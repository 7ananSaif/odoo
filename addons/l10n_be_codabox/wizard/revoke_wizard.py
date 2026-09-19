import requests
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.addons.l10n_be_codabox.const import get_error_msg


class L10n_Be_CodaboxRevokeWizard(models.TransientModel):
    _name = 'l10n_be_codabox.revoke.wizard'
    _description = 'CodaBox Revoke Wizard'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    company_vat = fields.Char(
        string='Company ID',
    )
    fiduciary_vat = fields.Char(
        string='Accounting Firm VAT',
        related='company_id.l10n_be_codabox_fiduciary_vat',
        readonly=True,
    )
    l10n_be_codabox_is_connected = fields.Boolean(related='company_id.l10n_be_codabox_is_connected')
    fidu_password = fields.Char(
        string='Accounting Firm Password',
        help='This is the password you have received from Odoo the first time you connected to CodaBox.'
             ' Check the documentation if you have forgotten your password.',
        groups="base.group_system",
    )
    nb_connections = fields.Integer()

    def l10n_be_codabox_revoke(self):
        self.company_id._l10n_be_codabox_verify_prerequisites()
        if not self.fidu_password:
            raise UserError(get_error_msg({"type": "error_invalid_fidu_password"}))
        try:
            params = self.company_id._l10n_be_codabox_get_iap_common_params()
            params["company_vat"] = self.company_id.l10n_be_codabox_company_vat
            params["fidu_password"] = self.fidu_password
            self.company_id._l10_be_codabox_call_iap_route("revoke", params)
            # We don't want to set the token and connection to false when revoking from another company's db
            if self.company_vat == (self.company_id.vat or self.company_id.company_registry):
                self.company_id.l10n_be_codabox_iap_token = False
                self.company_id.l10n_be_codabox_is_connected = False
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _('Information'),
                    'message': _('CodaBox connection revoked.'),
                    'next': {
                        'type': 'ir.actions.act_window_close'
                    },
                }
            }
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise UserError(get_error_msg({"type": "error_connecting_iap"}))
