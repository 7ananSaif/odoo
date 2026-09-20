from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _send_confirmation_email(self):
        super()._send_confirmation_email()
        # Sudo as the user has not always the right to read this WhatsApp template.
        pickings = self.filtered(lambda picking: (
            picking.company_id._get_text_validation('whatsapp')
            and picking.picking_type_id.code == 'outgoing'
            and picking.company_id.sudo().stock_confirmation_wa_template_id
        ))
        for wa_template, pickings in pickings.grouped(lambda p: p.company_id.sudo().stock_confirmation_wa_template_id).items():
            # Remove 'active_model' to prevent incorrect 'res_model' in whatsapp.composer's default_get,
            # as the picking might be opened from a different action like stock_picking_type_action.
            context = self.env.context.copy()
            context.pop('active_model', None)
            self.env['whatsapp.composer'].with_context(context).create({
                'batch_mode': len(pickings) > 1,
                'res_model': pickings._name,
                'res_ids': pickings.ids,
                'wa_template_id': wa_template.id,
            })._send_whatsapp_template(force_send_by_cron=True)
