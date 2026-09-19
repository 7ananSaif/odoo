from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _mail_get_partner_fields(self, introspect_fields=False):
        """Include partner field set automatically by studio as an SMS recipient."""
        fields = super()._mail_get_partner_fields(introspect_fields=introspect_fields)
        field = self._fields.get('x_studio_partner_id')
        if field and field.type == 'many2one' and field.comodel_name == 'res.partner':
            fields.append('x_studio_partner_id')
        return fields
