# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
from werkzeug.urls import url_join

from odoo import _, fields, models, tools, modules
from odoo.addons.account_edi_proxy_client.models.account_edi_proxy_user import AccountEdiProxyError
from odoo.exceptions import UserError, LockError
from ..exceptions import _l10n_au_raise_user_error

_logger = logging.getLogger(__name__)

DEFAULT_TEST_URL = 'http://127.0.0.1:8070'
DEFAULT_PROD_URL = 'http://127.0.0.1:8071'


class AccountEdiProxyClientUser(models.Model):
    _inherit = 'account_edi_proxy_client.user'

    proxy_type = fields.Selection(selection_add=[('l10n_au_payroll', 'Australian Payroll')], ondelete={'l10n_au_payroll': 'cascade'})

    # ----------------
    # Extends
    # ----------------

    def _get_proxy_urls(self):
        urls = super()._get_proxy_urls()
        urls['l10n_au_payroll'] = {
            'demo': False,
            'prod': self.env['ir.config_parameter'].get_param('l10n_au_payroll_iap.endpoint', DEFAULT_PROD_URL),
            'test': self.env['ir.config_parameter'].get_param('l10n_au_payroll_iap.test_endpoint', DEFAULT_TEST_URL),
        }
        return urls

    def _get_proxy_identification(self, company, proxy_type):
        if proxy_type == 'l10n_au_payroll':
            if not company.vat:
                raise UserError(_('Please fill the ABN of company "%(company_name)s" before enabling Australian Payroll Integration.',
                                  company_name=company.display_name))
            return f"{company.vat}:{company.name}"
        return super()._get_proxy_identification(company, proxy_type)

    def _l10n_au_register_proxy_user(self, company, edi_mode, registration_details):
        ''' Adapts the original _register_proxy_user method to the Australian Payroll needs.
        It creates a proxy user and the registers a client for that proxy user on the IAP server.

        :param registration_details: The client registration details for iap.
        '''
        proxy_type = "l10n_au_payroll"
        private_key_sudo = self.env['certificate.key'].sudo()._generate_rsa_private_key(
            company,
            name=f"{proxy_type}_{edi_mode}_{company.id}.key",
        )
        edi_identification = self._get_proxy_identification(company, proxy_type)
        if edi_mode == 'demo':
            # simulate registration
            response = {'id_client': f'demo{company.id}{proxy_type}', 'refresh_token': 'demo', 'client_bms_id': 'demo_bms_id'}
        else:
            try:
                # b64encode returns a bytestring, we need it as a string
                params = self._get_iap_params(company, proxy_type, private_key_sudo)
                params.update(
                    {
                        'registration_details': json.dumps(registration_details),
                        'registration_mode': edi_mode,
                    }
                )
                response = company._l10n_au_make_public_request(
                    '/connect', params=params,
                )
            except AccountEdiProxyError as e:
                raise UserError(e.message)
            if response.get('error_code', '') == 'iap_user_exists':
                raise UserError(_('A user already exists with theses credentials on our server. Please check your information.'))
            if 'error' in response:
                raise UserError(response['error'])

        company.l10n_au_bms_id = response['client_bms_id']
        return self.create({
            'id_client': response['id_client'],
            'company_id': company.id,
            'proxy_type': proxy_type,
            'edi_mode': edi_mode,
            'edi_identification': edi_identification,
            'private_key_id': private_key_sudo.id,
            'refresh_token': response['refresh_token'],
        })

    def _renew_token(self):
        if self.proxy_type != 'l10n_au_payroll':
            return super()._renew_token()

        try:
            self.lock_for_update()
        except LockError:
            return
        response = self._make_request(self._get_server_url() + '/api/l10n_au_payroll/1/renew_token')
        if 'error' in response:
            _logger.error(response['error'])
        self.sudo().refresh_token = response['refresh_token']

    # ----------------
    # Business methods
    # ----------------

    def _l10n_au_payroll_request(self, endpoint, params=None, handle_errors=True):
        if tools.config['test_enable'] or modules.module.current_test:
            raise UserError(_("Superchoice API Connection disabled in testing environment."))
        self.ensure_one()
        if not params:
            params = {}
        params.update(
             {
                "db_uuid": self.env['ir.config_parameter'].get_param('database.uuid'),
                "company_id": self.company_id.id,
                "client_bms_id": self.company_id.l10n_au_bms_id,
                "company_name": self.company_id.name,
                "company_abn": self.company_id.vat,
                "registration_mode": self.edi_mode,
            },
        )
        _logger.info({"endpoint": endpoint})
        try:
            response = self._make_request(
                url=url_join(self._get_server_url(), "/api/l10n_au_payroll/1" + endpoint),
                params=params,
            )
        except AccountEdiProxyError as _error:
            # Request error while contacting the IAP server. We assume it is a temporary error.
            _l10n_au_raise_user_error(_("Failed to contact the Australian Payroll service. Please try again later. %s", _error))

        if response.get("expired", False):
            registration = self.env["l10n_au.employer.registration"].search([
                ("company_id", "=", self.company_id.id),
                ("status", "=", "registered"),
            ])
            # Allow commiting the status change even if the main transaction is rolled back
            with self.env.registry.cursor() as new_cr:
                registration = registration.with_env(self.env(cr=new_cr))
                registration.sudo().status = "expired"

        if handle_errors and "error" in response:
            raise UserError(response["error"])
        return response
