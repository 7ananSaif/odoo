# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_in_gstr_gst_username = fields.Char(
        "GST username", related="company_id.l10n_in_gstr_gst_username", readonly=False
    )
    l10n_in_gstr_activate_einvoice_fetch = fields.Selection(
        related="company_id.l10n_in_gstr_activate_einvoice_fetch",
        readonly=False)
    l10n_in_gst_efiling_feature = fields.Boolean(related='company_id.l10n_in_gst_efiling_feature', readonly=False)
    l10n_in_fetch_vendor_edi_feature = fields.Boolean(
        related='company_id.l10n_in_fetch_vendor_edi_feature',
        readonly=False
    )
    l10n_in_enet_vendor_batch_payment_feature = fields.Boolean(
        related='company_id.l10n_in_enet_vendor_batch_payment_feature',
        readonly=False
    )
    l10n_in_gstr_gst_token_valid = fields.Boolean(compute='_compute_l10n_in_gstr_gst_token_valid')

    @api.depends('company_id')
    def _compute_l10n_in_gstr_gst_token_valid(self):
        for config in self:
            config.l10n_in_gstr_gst_token_valid = config.company_id._is_l10n_in_gstr_token_valid()

    def l10n_in_gstr_logout_gst(self):
        self.ensure_one()
        company = self.company_id
        response = self.env['account.return']._l10n_in_invalidate_gstr_token_request(company)
        _ = self.env._

        def _clear_gst_credentials():
            company.sudo().write({
                'l10n_in_gstr_gst_token': False,
                'l10n_in_gstr_gst_token_validity': False,
            })

        if not (error_response := response.get('error', [])):
            title = _("Logged Out Successfully")
            message = _("You have been successfully logged out from the GST portal.")
            notification_type = 'success'
            _clear_gst_credentials()
        elif any(error.get('code') == 'AUTH4033' for error in error_response):
            # AUTH4033: GSTIN is already logged out
            title = _("Already Logged Out")
            message = _("You have already logged out from the GST portal.")
            notification_type = 'info'
            _clear_gst_credentials()
        else:
            title = _("GST Logout Failed")
            message = "\n".join(
                "[%s] %s" % (error.get('code'), error.get('message'))
                for error in error_response
            )
            notification_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'sticky': False,
                'title': title,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
