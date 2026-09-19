from odoo import models


class MailTrackingValue(models.Model):
    _inherit = 'mail.tracking.value'

    def _tracking_value_format_model(self, model):
        """
        Different state fields for returns should have the label as "State" in the chatter.
        """
        formatted_list = super()._tracking_value_format_model(model)

        if model != 'account.return':
            return formatted_list

        formatted_map = {f['id']: f for f in formatted_list}
        return_map = {
            rec.id: rec.type_id.states_workflow for rec in self.env['account.return'].browse(self.mapped('mail_message_id.res_id'))
        }
        fields_string = self.env['ir.model.fields'].get_field_string('account.return')

        for tracking in self:
            if tracking.field_id.name == return_map.get(tracking.mail_message_id.res_id):
                formatted_map[tracking.id]['fieldInfo']['changedField'] = fields_string['state']
        return formatted_list
