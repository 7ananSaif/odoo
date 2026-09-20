from odoo import api, models


class SignDocument(models.Model):
    _name = 'sign.document'
    _inherit = ['sign.document', 'documents.unlink.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            attachment_id = vals.get('attachment_id')
            attachment = self.env['ir.attachment'].browse(attachment_id)

            if attachment:
                if attachment.res_model and attachment.res_model != 'documents.document':
                    # Attachment is linked to something else, then make a copy
                    vals['attachment_id'] = attachment.copy().id
                else:
                    # Unlink from documents.document or leave it unlinked
                    attachment.write({'res_model': False, 'res_id': 0})

        records = super().create(vals_list)

        for record in records:
            if record.attachment_id:
                record.attachment_id.write({
                    'res_model': record._name,
                    'res_id': record.id
                })

        return records
