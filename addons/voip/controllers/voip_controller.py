from werkzeug.exceptions import BadRequest, Forbidden, UnsupportedMediaType

from odoo import http
from odoo.fields import Domain
from odoo.http import Response, request

from odoo.addons.voip.models.utils import extract_country_code


class VoipController(http.Controller):
    @http.route("/voip/get_country_store", type="jsonrpc", auth="public", methods=["POST"])
    def get_country_store(self, phone_number):
        code = extract_country_code(phone_number)
        return request.env["res.country"]._get_country_by_country_code(code["iso"])

    @http.route("/voip/upload_recording/<int:call_id>", type="http", auth="user", methods=["POST"], csrf=True)
    def upload_recording(self, call_id, ufile):
        if not ufile:
            raise BadRequest()
        if not ufile.content_type.startswith("audio/"):
            raise UnsupportedMediaType()
        call_sudo = self.env["voip.call"].sudo().search_fetch(Domain("id", "=", call_id), limit=1)
        if request.env.user != call_sudo.user_id:
            raise Forbidden()
        attachment_sudo = (
            request.env["ir.attachment"]
            .sudo()
            ._from_request_file(
                file=ufile,
                mimetype="TRUST",
                res_model="voip.call",
                res_id=call_id,
            )
        )
        call_sudo.message_post(attachment_ids=[attachment_sudo.id])
        call_sudo.message_main_attachment_id = attachment_sudo.id
        return Response(status=200)
