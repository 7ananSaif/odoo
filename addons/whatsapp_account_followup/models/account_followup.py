from odoo import fields, models


class Account_FollowupFollowupLine(models.Model):
    _inherit = 'account_followup.followup.line'

    whatsapp_template_id = fields.Many2one(
        comodel_name='whatsapp.template',
        domain="[('model', '=', 'res.partner'), ('status', '=', 'approved')]",
    )
    send_whatsapp = fields.Boolean('WhatsApp')
