from odoo import http
from odoo.addons.account.controllers.download_docs import _get_headers
from odoo.http import request


class L10nBrEDIDownload(http.Controller):

    @http.route('/l10n_br_edi_pos/download_nfce_attachments/<models("ir.attachment"):attachments>', type='http', methods=['GET'], auth='user')
    def download_nfce_attachments(self, attachments):
        attachments.check_access('read')
        assert all(attachment.res_model == 'pos.order' and attachment.res_field == 'l10n_br_edi_xml_attachment_file' for attachment in attachments)
        filename = 'NFC-e_XML_Files.zip'
        content = attachments._build_zip_from_attachments()
        headers = _get_headers(filename, 'zip', content)
        return request.make_response(content, headers)
