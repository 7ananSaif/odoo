from datetime import timedelta
from unittest.mock import patch, ANY
from requests.exceptions import RequestException

from odoo.tests.common import TransactionCase, tagged
from odoo.addons.mail.tests.common import freeze_all_time
from odoo.addons.voip_ai.models.voip_call import _logger


@tagged("post_install", "-at_install")
class TestVoipAiCron(TransactionCase):
    """
    Part of the transcription subsystem testing that focuses on the Cron part in the flow.
    Tests in this class should check how cron performs given various preceding
    information (calls and their attachments) as well as external outcomes (api calls).
    Without actually calling external services.

    Since the cron doesn't commit in tests, we stay in the current cursor/env.

    Frontend                Backend Controller                      Cron
    ┌───────────────────┐   ┌──────────────────────────────────┐   ┌─────────────────────────────────────────┐
    │                   │   │                                  │   │ Finds recent call                       │
    │ Call Established  │   │ Checks file and access rights    │   │                                         │
    │                   │   │                                  │   │ Identifies related most recent recording│
    │ Recorder Started  │   │ Updates call transcription status│   │                                         │
    │                   │   │                                  │   │ Updates call transcription status       │
    │ Call Finished     │   │ Schedules cron                   │   │                                         │
    │                   │   │                                  │   │ Requests transcription                  │
    │ Recording Uploaded│   │                                  │   │                                         │   ┌─────────────┐
    └───────────────────┘   └──────────────────────────────────┘   │ Updates call transcription txt          │   │External api │
                                                                   └─────────────────────────────────────────┘   └─────────────┘
                                 ▲                                      ▲                          ▲            ▲   │
                    └────────────┘                        └──── . . . ───┘                           │   └─────────┘    │
               Recording File & Call id                                                              │      Audio       │
                                                     Recording attached to a call                    └──────────────────┘
                                                        with pending transcription                      Transcription txt
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Test User",
            "login": "test_user",
            "email": "test@example.com",
            "password": "password",
        })
        cls.audio_data = b"RIFF\x00\x00\x00\x00WAVEfmt\x00data\x00\x00\x00\x00"

    def setUp(self):
        super().setUp()
        self.get_transcription_patcher = patch("odoo.addons.ai.utils.llm_api_service.LLMApiService.get_transcription", autospec=True)
        self.get_direct_response_patcher = patch("odoo.addons.ai.models.ai_agent.AIAgent.get_direct_response", autospec=True)
        self.mock_get_transcription_api = self.get_transcription_patcher.start()
        self.mock_get_direct_response_api = self.get_direct_response_patcher.start()
        self.addCleanup(self.get_transcription_patcher.stop)
        self.addCleanup(self.get_direct_response_patcher.stop)
        self.call = self.env["voip.call"].create({
            "phone_number": "+1234567890",
            "user_id": self.user.id,
        })

    def test_cron_transcribe_recent_voip_call_happy_path(self):
        """Pending call with one recording => transcribed."""
        self.mock_get_transcription_api.return_value = "Fake response from transcription api"
        self.env["ir.attachment"].create({
            "name": "call_recording.ogg",
            "res_model": "voip.call",
            "res_id": self.call.id,
            "type": "binary",
            "mimetype": "audio/ogg",
            "raw": self.audio_data,
        })
        self.call.transcription_status = "pending"
        self.env["voip.call"]._cron_transcribe_recent_voip_call()
        self.assertEqual(self.call.transcription_status, "done")
        self.assertIn("Fake response from transcription api", self.call.transcript)
        self.mock_get_transcription_api.assert_called_once_with(ANY, self.audio_data, "audio/ogg")
        self.mock_get_direct_response_api.assert_called_once()

    def test_cron_transcribe_recent_voip_call_no_pending_calls(self):
        """No pending calls => nothing happens."""
        self.call.transcription_status = "done"
        self.env["voip.call"]._cron_transcribe_recent_voip_call()
        self.assertEqual(self.call.transcription_status, "done")
        self.mock_get_transcription_api.assert_not_called()
        self.mock_get_direct_response_api.assert_not_called()

    def test_cron_transcribe_recent_voip_call_no_audio(self):
        """Pending call without audio => status 'no_audio'."""
        self.call.transcription_status = "pending"

        self.env["voip.call"]._cron_transcribe_recent_voip_call()

        self.assertEqual(self.call.transcription_status, "no_audio")
        self.assertFalse(self.call.transcript)
        self.mock_get_transcription_api.assert_not_called()
        self.mock_get_direct_response_api.assert_not_called()

    def test_cron_transcribe_recent_voip_call_api_error(self):
        """External API fails => status 'error', log error, no transcript."""
        self.mock_get_transcription_api.side_effect = RequestException("This API Error is Expected")
        self.env["ir.attachment"].create({
            "name": "call_recording.ogg",
            "res_model": "voip.call",
            "res_id": self.call.id,
            "type": "binary",
            "mimetype": "audio/ogg",
            "raw": self.audio_data,
        })
        self.call.transcription_status = "pending"

        with self.assertLogs(_logger, "ERROR") as cm:
            self.env["voip.call"]._cron_transcribe_recent_voip_call()
            self.assertIn(f"Call {self.call.id}: transcription failed", cm.output[0])

        self.assertEqual(self.call.transcription_status, "error")
        self.assertFalse(self.call.transcript)
        self.mock_get_transcription_api.assert_called_once_with(ANY, self.audio_data, "audio/ogg")
        self.mock_get_direct_response_api.assert_not_called()

    def test_cron_transcribe_recent_voip_call_multiple_recordings(self):
        """Multiple recordings => warn and use the newest one."""
        self.mock_get_transcription_api.return_value = "Newest transcript."
        self.call.transcription_status = "pending"

        # Older recording
        with freeze_all_time("2023-01-01 00:00:00"):
            self.env["ir.attachment"].create({
                "name": "old_recording.ogg",
                "res_model": "voip.call",
                "res_id": self.call.id,
                "type": "binary",
                "mimetype": "audio/ogg",
                "raw": b"old_audio",
            })
        # Newest recording
        with freeze_all_time("2023-01-01 00:00:05"):
            self.env["ir.attachment"].create({
                "name": "new_recording.ogg",
                "res_model": "voip.call",
                "res_id": self.call.id,
                "type": "binary",
                "mimetype": "audio/ogg",
                "raw": self.audio_data,
            })

        with self.assertLogs(_logger, "WARNING") as cm:
            self.env["voip.call"]._cron_transcribe_recent_voip_call()
            self.assertIn(f"Call {self.call.id} has multiple recordings; processing only the newest one", cm.output[0])

        self.assertEqual(self.call.transcription_status, "done")
        self.assertIn("Newest transcript.", self.call.transcript)
        self.mock_get_transcription_api.assert_called_once_with(ANY, self.audio_data, "audio/ogg")
        self.mock_get_direct_response_api.assert_called_once()

    def test_cron_transcribe_recent_voip_call_two_calls_at_same_time(self):
        """Two pending calls => cron transcribes both (run twice)."""
        call1 = self.call

        # Make call2 older so call1 is processed first (stable side-effect order).
        with freeze_all_time(call1.create_date - timedelta(seconds=1)):
            call2 = self.env["voip.call"].create({
                "phone_number": "+1987654321",
                "user_id": self.user.id,
            })

        with freeze_all_time():
            call1.write({"transcription_status": "pending"})
            call2.write({"transcription_status": "pending"})
            self.env["ir.attachment"].create({
                "name": "call1_recording.ogg",
                "res_model": "voip.call",
                "res_id": call1.id,
                "type": "binary",
                "mimetype": "audio/ogg",
                "raw": self.audio_data,
            })
            self.env["ir.attachment"].create({
                "name": "call2_recording.ogg",
                "res_model": "voip.call",
                "res_id": call2.id,
                "type": "binary",
                "mimetype": "audio/ogg",
                "raw": self.audio_data,
            })

        self.mock_get_transcription_api.side_effect = ["Transcript for call 1", "Transcript for call 2"]

        self.env["voip.call"]._cron_transcribe_recent_voip_call()
        self.env["voip.call"]._cron_transcribe_recent_voip_call()

        self.assertEqual(call1.transcription_status, "done")
        self.assertIn("Transcript for call 1", call1.transcript)
        self.assertEqual(call2.transcription_status, "done")
        self.assertIn("Transcript for call 2", call2.transcript)

        self.assertEqual(self.mock_get_transcription_api.call_count, 2)
        self.assertEqual(self.mock_get_direct_response_api.call_count, 2)

        self.mock_get_transcription_api.assert_any_call(ANY, self.audio_data, "audio/ogg")
