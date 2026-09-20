# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SignSendRequest(models.TransientModel):
    _inherit = 'sign.send.request'

    is_whatsapp_feature_enabled = fields.Boolean(compute="_compute_is_whatsapp_feature_enabled")

    @api.depends('template_id')
    def _compute_is_whatsapp_feature_enabled(self):
        """
        Checks if all required WhatsApp templates are configured and approved.
        """
        self.is_whatsapp_feature_enabled = self.env['sign.request.item']._check_whatsapp_template_exists(check_if_approved=True)

    def send_via_whatsapp(self):
        self.ensure_one()
        self._check_whatsapp_requirements()
        request = self.with_context(send_channel='whatsapp').create_request()
        return self._create_log_and_close(request)

    def _check_whatsapp_requirements(self):
        signers = self.signer_ids.mapped('partner_id')
        if any(not signer.phone for signer in signers):
            raise UserError(_("All signers must have a phone number to send messages via WhatsApp."))
