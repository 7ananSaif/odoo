# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request, content_disposition


class StarshipitDocumentDownloadController(http.Controller):

    @http.route('/delivery_starshipit/download_starshipit_labels/<models("ir.attachment"):attachments>', type='http', auth='user')
    def download_invoice_attachments(self, attachments):
        attachments.check_access('read')
        assert all(attachment.res_id and attachment.res_model == 'stock.picking' for attachment in attachments)
        if len(attachments) == 1:
            return request.make_response(attachments.raw, [
                ('Content-Type', attachments.mimetype),
                ('Content-Length', len(attachments.raw)),
                ('Content-Disposition', content_disposition(attachments.name)),
                ('X-Content-Type-Options', 'nosniff'),
            ])
        else:
            filename = self.env._('starshipit_labels') + '.zip'
            content = attachments._build_zip_from_attachments()
            return request.make_response(content, [
                ('Content-Type', 'zip'),
                ('Content-Length', len(content)),
                ('Content-Disposition', content_disposition(filename)),
                ('X-Content-Type-Options', 'nosniff'),
            ])
