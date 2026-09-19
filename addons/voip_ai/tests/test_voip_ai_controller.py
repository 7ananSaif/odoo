from unittest.mock import patch

from odoo import http
from odoo.fields import Command
from odoo.tests.common import HttpCase, tagged
from odoo.addons.voip_ai.controllers.voip_ai_controller import TRANSCRIPTION_MAX_FILE_SIZE


@tagged("post_install", "-at_install")
class TestVoipAiController(HttpCase):
    """
    Part of the transcription subsystem testing that focus on the Backend Controller part in the flow depicted here.
    Thus most tests in this class should assume finished call and some sort of request for transcription.

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
        cls.patcher = patch(
            "odoo.addons.base.models.ir_cron.IrCron._trigger", autospec=True
        )
        cls.mock_trigger = cls.patcher.start()
        cls.addClassCleanup(cls.patcher.stop)

        cls.user = cls.env["res.users"].create({
                "name": "Test Calling Agent User",
                "login": "test_user",
                "email": "test@example.com",
                "password": "test_user",
        })
        cls.WAV_HEADER_STUB_BYTES = b"RIFF\x00\x00\x00\x00WAVEfmt\x00data\x00\x00\x00\x00"

    def setUp(self):
        super().setUp()
        self.mock_trigger.reset_mock()

        # Simulates a call that has just ended
        self.voip_call = self.env["voip.call"].create({
                "phone_number": "+1234567890",
                "user_id": self.user.id,
                "transcription_status": "no_audio",
        })

    def test_transcribe_call_happy_path(self):
        """ Given existing recording file and a finished call,
            the transcribe route should create an attachment and trigger cron.
        """
        self.authenticate(self.user.login, self.user.login)
        response = self.url_open(
            f"/voip_ai/transcribe/{self.voip_call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("recording.ogg", self.WAV_HEADER_STUB_BYTES, "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, 200, "Should return 200 OK on successful transcription request")
        self.assertEqual(self.voip_call.transcription_status, "pending",
            "Transcription status should be 'pending' after successful upload")
        attachment = self.env["ir.attachment"].search([
            ("res_model", "=", "voip.call"),
            ("res_id", "=", self.voip_call.id),
            ("mimetype", "=", "audio/ogg"),
        ])
        self.assertTrue(attachment, "An attachment should be created for the recording")
        self.assertEqual(attachment.raw, self.WAV_HEADER_STUB_BYTES,
            "Attachment content should match the uploaded recording")
        self.mock_trigger.assert_called_once()

    def test_cant_transcribe_call_without_input_file(self):
        self.authenticate(self.user.login, self.user.login)
        response = self.url_open(
            f"/voip_ai/transcribe/{self.voip_call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("", "", "")},
            method="POST",
        )
        self.assertEqual(response.status_code, 400, "Can't transcribe call without the call recording given")
        self.mock_trigger.assert_not_called()

    def test_cant_transcribe_already_transcribed_calls(self):
        self.voip_call.transcription_status = 'done'
        self.authenticate(self.user.login, self.user.login)
        response = self.url_open(
            f"/voip_ai/transcribe/{self.voip_call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("recording.ogg", self.WAV_HEADER_STUB_BYTES, "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, 403, "Can't request transcription for an already transcribed call")
        self.mock_trigger.assert_not_called()

    def test_cant_transcribe_call_with_file_too_large(self):
        self.authenticate(self.user.login, self.user.login)
        large_audio_data = b"A" * (TRANSCRIPTION_MAX_FILE_SIZE + 1)  # 25MB + 1 byte
        response = self.url_open(
            f"/voip_ai/transcribe/{self.voip_call.id}",
            data={"csrf_token": http.Request.csrf_token(self)},
            files={"ufile": ("recording.ogg", large_audio_data, "audio/ogg")},
            method="POST",
        )
        self.assertEqual(response.status_code, 413, "Can't request transcription for too large files")  # RequestEntityTooLarge
        self.assertEqual(
            self.voip_call.transcription_status,
            "too_big_to_process",
            "Transcription of too large file should set appropriate status on call",
        )
        self.mock_trigger.assert_not_called()

    def test_user_cant_transcribe_call_without_read_rights(self):
        no_access_user = self.env["res.users"].create({
            "name": "No Access User",
            "login": "no_access_user",
            "password": "no_access_user",
            "email": "no_access@example.com",
        })
        no_access_user.write({"group_ids": [Command.clear()]})
        self.authenticate(no_access_user.login, no_access_user.login)
        with self.assertLogs("odoo.http", level="WARNING") as cm:
            response = self.url_open(
                f"/voip_ai/transcribe/{self.voip_call.id}",
                data={"csrf_token": http.Request.csrf_token(self)},
                files={"ufile": ("recording.ogg", self.WAV_HEADER_STUB_BYTES, "audio/ogg")},
                method="POST",
            )
            self.assertEqual(response.status_code, 403, "Only users able to read voip calls should be able to request transcriptions")
            self.assertIn("You are not allowed to access 'Phone call' (voip.call) records.", cm.output[0])
        self.mock_trigger.assert_not_called()
