from werkzeug.exceptions import BadRequest, Forbidden

from odoo import http
from odoo.http import Response, request

# Based on OpenAI Transcriptions API limits
# https://platform.openai.com/docs/guides/speech-to-text#longer-inputs
TRANSCRIPTION_MAX_FILE_SIZE = 25 * 1024 * 1024


class VoipAiController(http.Controller):
    @http.route("/voip_ai/transcribe/<models('voip.call'):call>", type="http", auth="user", methods=["POST"], csrf=True)
    def transcribe_call(self, call, ufile):
        call.ensure_one()
        if not ufile:
            raise BadRequest()
        if call.transcription_status != "no_audio":
            # Prevent tampering with existing transcripts.
            raise Forbidden()
        call.with_user(request.session.uid).check_access("read")
        # sudo: read perms checked ✅ - base.group_user can't write to voip.call
        call_sudo = call.sudo()
        recording_raw = ufile.read()
        if len(recording_raw) > TRANSCRIPTION_MAX_FILE_SIZE:
            call_sudo.transcription_status = "too_big_to_process"
            return request.make_response("Recording too large", status=413, headers=[("Content-Type", "text/plain")])
        request.env["ir.attachment"].sudo().create(
            {
                "name": "call_recording.ogg",
                "res_model": "voip.call",
                "res_id": call_sudo.id,
                "type": "binary",
                "mimetype": "audio/ogg",
                "raw": recording_raw,
            }
        )
        call_sudo.transcription_status = "pending"
        request.env.ref("voip_ai.ir_cron_transcribe_recent_voip_call").sudo()._trigger()
        return Response(status=200)
