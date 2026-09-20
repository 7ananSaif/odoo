from json.decoder import JSONDecodeError
from logging import getLogger

from requests.exceptions import RequestException

from odoo import api, fields, models, modules
from odoo.exceptions import UserError
from odoo.addons.ai.utils.llm_api_service import LLMApiService

_logger = getLogger(__name__)


class VoipCall(models.Model):
    _inherit = "voip.call"

    transcript = fields.Text()
    transcription_status = fields.Selection(
        [
            ("pending", "Pending"),  # waiting for cron
            ("queued", "Queued"),  # picked by cron, might get stuck in this state
            ("done", "Done"),  # success
            ("error", "Error"),  # API failure
            ("too_big_to_process", "Too long to process"),  # >25 MB
            ("no_audio", "No audio"),  # attachment missing
        ],
        default="no_audio",
        copy=False,
        index=True,
    )
    summary = fields.Char(string="Summary", copy=False)

    @api.model
    def _cron_transcribe_recent_voip_call(self):
        call = self.search(
            [("transcription_status", "=", "pending")],
            order="create_date desc",
            limit=1,
        )
        if not call:
            return
        call.transcription_status = "queued"
        if not modules.module.current_test:
            self.env.cr.commit()
        domain = [
            ("res_model", "=", "voip.call"),
            ("res_id", "=", call.id),
            ("mimetype", "=", "audio/ogg"),
        ]
        recordings = self.env["ir.attachment"].search(domain, order="create_date desc")

        if not recordings:
            call.transcription_status = "no_audio"
            return

        if len(recordings) > 1:
            _logger.warning(
                "Call %s has multiple recordings; processing only the newest one (%s).", call.id, recordings[0].id
            )

        recording = recordings[0]

        try:
            text = LLMApiService(self.env).get_transcription(recording.raw, "audio/ogg")
        except (RequestException, JSONDecodeError, UserError):
            _logger.exception("Call %s: transcription failed", call.id)
            call.transcription_status = "error"
            return

        call.transcript = (call.transcript or "") + text
        call.transcription_status = "done"

        # Generate one-liner summary
        try:
            ai_agent = self.env.ref('voip_ai.voip_call_summary_agent', raise_if_not_found=False)
            if call.transcript:
                summary_response = ai_agent.get_direct_response(prompt=call.transcript)
                if summary_response:
                    call.summary = summary_response[0]
        except (RequestException, JSONDecodeError, UserError):
            _logger.exception("Call %s: one-liner summary generation failed", call.id)
