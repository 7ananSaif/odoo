import base64

from odoo import fields, models
from odoo.tools.pdf.signature import PdfSigner


class SignCompletedDocument(models.Model):
    _name = 'sign.completed.document'
    _description = "Completed Document"

    sign_request_id = fields.Many2one('sign.request', string="Sign Request", required=True, index=True, ondelete='restrict')
    file = fields.Binary(readonly=True, string="Completed Document", attachment=True, copy=False)
    document_id = fields.Many2one('sign.document', string="Document", required=True, index=True, ondelete='restrict')

    def _generate_completed_document(self):
        for record in self:
            itemsByPage = record.document_id._get_sign_items_by_page()
            item_ids = [id for items in itemsByPage.values() for id in items.ids]
            values_dict = self.env['sign.request.item.value']._read_group(
                [('sign_item_id', 'in', item_ids), ('sign_request_id', '=', record.sign_request_id.id)],
                groupby=['sign_item_id'],
                aggregates=['value:array_agg', 'frame_value:array_agg', 'frame_has_hash:array_agg']
            )
            signed_values = {
                sign_item.id: {
                    'value': values[0],
                    'frame': frame_values[0],
                    'frame_has_hash': frame_has_hashes[0],
                }
                for sign_item, values, frame_values, frame_has_hashes in values_dict
            }
            final_log_hash = record.sign_request_id._get_final_signature_log_hash()
            output = record.document_id.render_document_with_items(signed_values=signed_values, values_dict=values_dict, final_log_hash=final_log_hash)
            signer = PdfSigner(output, record.sign_request_id.communication_company_id)
            signed_output = signer.sign_pdf(True, record.sign_request_id._get_signing_field_name(), record.sign_request_id.create_uid.partner_id)
            if signed_output:
                output = signed_output
            record.file = base64.b64encode(output.getvalue())
            output.close()
