from odoo import api, fields, models


class Account_FollowupManual_Reminder(models.TransientModel):
    _name = 'account_followup.manual_reminder'
    _inherit = ['account_followup.manual_reminder', 'whatsapp.composer']

    def _raise_no_template_error(self, res_model):
        # OVERRIDE whatsapp.composer
        return

    whatsapp = fields.Boolean()
    attachment_id = fields.Many2one('ir.attachment', string="WhatsApp attachment", index=True)

    @api.depends('whatsapp')
    def _compute_show_send_button(self):
        # EXTENDS account_followup.manual_reminder
        super()._compute_show_send_button()
        for wizard in self:
            wizard.show_send_button = wizard.show_send_button or wizard.whatsapp

    @api.depends('partner_id')
    def _compute_number(self):
        # OVERRIDE whatsapp.composer
        for composer in self:
            composer.phone = composer.partner_id._get_followup_whatsapp_number()

    def _get_wizard_options(self):
        # EXTENDS account_followup.manual_reminder
        options = super()._get_wizard_options()
        options['whatsapp'] = self.whatsapp
        options['whatsapp_composer'] = self
        return options
