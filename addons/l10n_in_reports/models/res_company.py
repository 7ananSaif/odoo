# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import RedirectWarning


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_in_gstr_gst_username = fields.Char(string="GST User Name (IN)", groups="base.group_system")
    l10n_in_gstr_gst_token = fields.Char(string="GST Token (IN)", groups="base.group_system")
    l10n_in_gstr_gst_token_validity = fields.Datetime(string="GST Token (IN) Valid Until", groups="base.group_system")
    l10n_in_gstr_activate_einvoice_fetch = fields.Selection(
        string='Fetch Vendor E-Invoiced Documents',
        selection=[
            ('manual', 'Fetch Manually'),
            ('automatic', 'Fetch Automatically'),
        ],
        default='manual',
        help="""
            Fetch Manually - Invoices are created without lines but an IRN number, but there is a button to get the lines.
            Fetch Automatically - Existing documents with an IRN are automatically updated, and incoming documents are fetched and populated automatically."""
    )
    l10n_in_gst_efiling_feature = fields.Boolean(string="GST E-Filing & Matching Feature")
    l10n_in_fetch_vendor_edi_feature = fields.Boolean(string="Fetch Vendor E-Invoiced Document")
    l10n_in_enet_vendor_batch_payment_feature = fields.Boolean(string="ENet Vendor Batch Payment")

    def _is_l10n_in_gstr_token_valid(self):
        self.ensure_one()
        return (
            self.sudo().l10n_in_gstr_gst_token_validity
            and self.sudo().l10n_in_gstr_gst_token_validity > fields.Datetime.now()
        )

    def _check_tax_return_configuration(self):
        """
        Check if the e-filling feature is enabled in configuration for tax returns.
        :raises RedirectWarning: if something is wrong configured.
        """

        if self.country_code != 'IN':
            return super()._check_tax_return_configuration()

        if not self.l10n_in_gst_efiling_feature:
            msg = self.env._("First enable GST e-Filing feature from configuration for company %s.", (self.name))
            action = self.env.ref("account.action_account_config")
            raise RedirectWarning(msg, action.id, self.env._('Go to configuration'))
