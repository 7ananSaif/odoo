import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.l10n_at_pos.models.fiskaly_client import FiskalyClient, fiskaly_iap_rpc


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_at_pos_is_tax_exempted = fields.Boolean(string="Tax exempted?", default=False, copy=False)
    l10n_at_pos_test_mode = fields.Boolean(string="Test Fiskaly", default=True, copy=False)
    # Fiskaly api fields
    l10n_at_fiskaly_api_key = fields.Char(string="Fiskaly API Key (AUT)", copy=False)
    l10n_at_fiskaly_api_secret = fields.Char(string="Fiskaly API Secret (AUT)", copy=False)
    l10n_at_fiskaly_access_token = fields.Char(string="API Access Token", copy=False)
    l10n_at_fiskaly_organization_id = fields.Char(string="Fiskaly organization identifier", copy=False)
    l10n_at_is_odoo_managed_org = fields.Boolean(string="Managed By Odoo", default=True, copy=False)
    # FON fields
    l10n_at_fon_participant_id = fields.Char(string="Participation Identifier", copy=False)
    l10n_at_fon_user_id = fields.Char(string="User Identifier", copy=False)
    l10n_at_fon_user_pin = fields.Char(string="User Pin", copy=False)
    l10n_at_is_fon_authenticated = fields.Boolean(string="FON Authenticated?", copy=False)
    # Company SCU
    l10n_at_pos_company_scuid = fields.Char(string="Fiskaly SCU id (uuid)", readonly=True, copy=False)

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields += ["l10n_at_is_fon_authenticated"]
        return fields

    def _l10n_at_create_db_payload(self, db_uuid):
        params = {'db_uuid': db_uuid, 'company_id': self.id}
        if self.l10n_at_fiskaly_organization_id:
            params['organization_id'] = self.l10n_at_fiskaly_organization_id
        return params

    def _l10n_at_create_organization_payload(self):
        self._l10n_at_check_required_fiskaly_fields()
        db_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        data = {
            'name': f'{self.name} [#{db_uuid}]',  # To make sure the name is always unique
            'vat_id': self.vat,
            'display_name': self.display_name,
            'address_line1': self.street,
            'address_line2': self.street2,
            'town': self.city,
            'state': self.state_id.name,
            'zip': self.zip,
            'email': self.email,
            'country_code': 'AUT',
        }
        return {'data': data, **self._l10n_at_create_db_payload(db_uuid)}

    def _l10n_at_check_required_fiskaly_fields(self):
        msg = ""
        if len(self.name) < 3:
            msg = _("The name should be at least 3 characters long")
        if not self.street or not self.street.strip():
            msg = _("The street should not be empty")
        if not self.zip or not self.zip.strip():
            msg = _("The zip should not be empty")
        if not self.city or not self.city.strip():
            msg = _("The city should not be empty")
        if not self.vat or not self.vat.strip():
            msg = _("The VAT should not be empty")
        if msg:
            raise UserError(msg)

    def write(self, vals):
        # ensuring values are correct
        msg = ""
        if vals.get('l10n_at_fon_participant_id') and len(vals.get('l10n_at_fon_participant_id')) < 8:
            msg = _("FON participation id should NOT be shorter than 8 characters, please enter correct participation id")
        if vals.get('l10n_at_fon_user_id') and len(vals.get('l10n_at_fon_user_id')) < 5:
            msg = _("FON user id should NOT be shorter than 5 characters, please enter correct user id")
        if vals.get('l10n_at_fon_user_pin') and len(vals.get('l10n_at_fon_user_pin')) < 5:
            msg = _("FON user id should NOT be shorter than 5 characters, please verify your pin")
        if msg:
            raise UserError(msg)

        # If necessary fields are removed, need to authenticate again
        if any(key in vals for key in ('l10n_at_fiskaly_api_key', 'l10n_at_fiskaly_api_secret')) and self.l10n_at_fiskaly_access_token:
            vals.update({"l10n_at_fiskaly_access_token": ""})

        if any(key in vals for key in ('l10n_at_fon_participant_id', 'l10n_at_fon_user_id', 'l10n_at_fon_user_pin')) and self.l10n_at_is_fon_authenticated:
            # If any necessary fields are removed, need authentication again
            vals.update({"l10n_at_is_fon_authenticated": False})

        companies = super().write(vals)
        for company in self:
            if company.country_code == 'AT' and company.l10n_at_fiskaly_organization_id and company.l10n_at_is_odoo_managed_org:
                on_change_fields = ['name', 'street', 'street2', 'zip', 'city', 'vat', 'state_id', 'email']
                if set(on_change_fields) & set(vals):
                    params = company._l10n_at_create_organization_payload()
                    fiskaly_iap_rpc(self, '/update', params)
        return companies

    def action_l10n_at_authenticate_fon_credentials(self):
        self.ensure_one()
        fiskaly_client = FiskalyClient(self, self.l10n_at_fiskaly_api_key, self.l10n_at_fiskaly_api_secret)
        if open_sessions := self.env['pos.session'].search([('company_id', '=', self.id), ('state', '!=', 'closed')]):
            raise UserError(_('Please close and validate the following open PoS Sessions before authenticating FON.\n'
                            'Open sessions: %s', (' '.join(open_sessions.mapped('name')),)))

        fiskaly_client = FiskalyClient(self, self.l10n_at_fiskaly_api_key, self.l10n_at_fiskaly_api_secret)
        fiskaly_client.fon_auth(
            bearer_token=self.l10n_at_fiskaly_access_token,
            data={
                "fon_participant_id": self.l10n_at_fon_participant_id,
                "fon_user_id": self.l10n_at_fon_user_id,
                "fon_user_pin": self.l10n_at_fon_user_pin,
            }
        )
        self.l10n_at_is_fon_authenticated = True

        # Check if any existing configs which needs to be registered
        pos_configs = self.env['pos.config'].search([('company_id', '=', self.id), ('l10n_at_cash_regid', '=', False)])
        for pos_config in pos_configs:
            pos_config._configure_register()
        return self._notify("success", _("FON Authenticated Successfully!"))

    def action_generate_fiskaly_credentials(self):
        self.ensure_one()
        params = self._l10n_at_create_organization_payload()
        response = fiskaly_iap_rpc(self, '/register', params)
        self.write({
            'l10n_at_fiskaly_organization_id': response[0]['organization_id'],
            'l10n_at_fiskaly_api_key': response[0]['l10n_at_fiskaly_api_key'],
            'l10n_at_fiskaly_api_secret': response[0]['l10n_at_fiskaly_api_secret'],
        })

    def action_auth_fiskaly_credentials(self, refresh=False):
        """Authenticate with Fiskaly and store the access token."""
        self.ensure_one()
        fiskaly_client = FiskalyClient(self, self.l10n_at_fiskaly_api_key, self.l10n_at_fiskaly_api_secret)
        self.l10n_at_fiskaly_access_token = fiskaly_client.auth()
        return self._notify("success", _("Fiskaly Authenticated Successfully!"))

    def _verify_required_fields(self):
        missing_fields_by_company = {}
        for company in self:
            if company.l10n_at_fiskaly_access_token:
                missing_fields = [label for field, label in [
                        (company.vat, _("VAT")),
                        (company.street, _("Street")),
                        (company.country_id, _("Country"))
                    ] if not field]

                if missing_fields:
                    missing_fields_by_company[company.name] = ", ".join(missing_fields)
        if missing_fields_by_company:
            message = "\n".join(
                f"Company {company} has these fields missing: {fields}"
                for company, fields in missing_fields_by_company.items()
            )
            raise ValidationError(_("The following companies have missing details required to use Fiskaly:\n%s", message))

        # Austria vat format check
        if not re.match(r"^ATU\d{8}$", self.vat):
            raise UserError(_("Please enter a valid Austrian VAT number in the format ATU12345678"))

    def _notify(self, notification_type, message=""):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
