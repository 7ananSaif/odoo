# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from requests.exceptions import HTTPError, ConnectionError, MissingSchema, Timeout
from urllib3.exceptions import NewConnectionError
from werkzeug.urls import url_join

from odoo import api, models, fields, _, tools, modules
from odoo.exceptions import ValidationError, UserError
from ..exceptions import _l10n_au_raise_user_error

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = ["res.company", "l10n_au.audit.logging.mixin"]

    l10n_au_payroll_proxy_user_id = fields.Many2one(
        comodel_name="account_edi_proxy_client.user",
        compute="_compute_l10n_au_payroll_proxy_user_id",
    )
    l10n_au_payroll_mode = fields.Selection(
        selection=[
            ('test', 'Testing'),
            ('prod', 'Production'),
        ],
        string="Payroll Mode",
        default="test",
        required=True
    )
    l10n_au_abn_valid = fields.Boolean("ABN Validation State", readonly=True, tracking=True)
    l10n_au_employer_registration_ids = fields.One2many(
        comodel_name="l10n_au.employer.registration",
        inverse_name="company_id",
        string="Employer Registration",
    )
    l10n_au_employer_registration_id = fields.Many2one(
        comodel_name="l10n_au.employer.registration",
        string="Current Employer Registration",
        compute="_compute_l10n_au_employer_registration_id",
        store=True,
    )
    l10n_au_registration_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('ongoing', 'Ongoing'),
            ('registered_ongoing', 'Registered (Ongoing)'),
            ('registered', 'Registered'),
            ('expired', 'Expired'),
        ],
        string="Registration Status",
        compute="_compute_l10n_au_employer_registration",
    )

    # --------------------------------
    # ORM methods
    # --------------------------------
    def write(self, vals):
        if "vat" in vals or "name" in vals:
            self.l10n_au_abn_valid = False
        return super().write(vals)

    @api.depends("account_edi_proxy_client_ids", 'l10n_au_payroll_mode')
    def _compute_l10n_au_payroll_proxy_user_id(self):
        """ Each company is expected to have at most one proxy user for malaysia for each mode.
        Thus, we can easily find said user.
        """
        for company in self:
            company.l10n_au_payroll_proxy_user_id = company.account_edi_proxy_client_ids.filtered(
                lambda u: u.proxy_type == 'l10n_au_payroll' and u.edi_mode == company.l10n_au_payroll_mode
            )

    @api.depends("l10n_au_employer_registration_ids", "l10n_au_employer_registration_ids.status")
    def _compute_l10n_au_employer_registration_id(self):
        """ It uses the latest registered registration if available, otherwise it
            falls back to the most recent one.
        """
        for record in self:
            record.l10n_au_employer_registration_id = record.l10n_au_employer_registration_ids.filtered(
                lambda r: r.status == 'registered'
            ) or record.l10n_au_employer_registration_ids.sorted(
                key=lambda r: r.create_date, reverse=True
            )[:1]

    @api.depends("l10n_au_employer_registration_ids", "l10n_au_employer_registration_ids.status")
    def _compute_l10n_au_employer_registration(self):
        for record in self:
            if not record.l10n_au_employer_registration_ids:
                record.l10n_au_registration_status = 'pending'
            else:
                latest_registration = record.l10n_au_employer_registration_ids.sorted(
                    key=lambda r: r.create_date, reverse=True
                )[0]
                if latest_registration.status == 'pending':
                    if record.l10n_au_employer_registration_id.status == 'registered':
                        record.l10n_au_registration_status = 'registered_ongoing'
                    else:
                        record.l10n_au_registration_status = 'ongoing'
                else:
                    record.l10n_au_registration_status = latest_registration.status

    # --------------------------------
    # Business methods
    # --------------------------------

    def _l10n_au_make_public_request(self, endpoint, params=None, timeout=30):
        """ Make a public http request to Payroll Proxy server. """
        if tools.config['test_enable'] or modules.module.current_test:
            raise UserError(_("Superchoice API Connection disabled in testing environment."))
        host = self.env["account_edi_proxy_client.user"]._get_server_url("l10n_au_payroll", self.l10n_au_payroll_mode or "test")
        params = params or {}
        params.update({
            "db_uuid": self.env['ir.config_parameter'].get_param('database.uuid'),
        })
        try:
            response = requests.get(
                url=url_join(host, "/api/l10n_au_payroll/1" + endpoint),
                params=params,
                timeout=timeout
            )
            response = response.json()
        except (ConnectionError, MissingSchema, Timeout, HTTPError, NewConnectionError) as e:
            _l10n_au_raise_user_error(e)
        return response

    def _l10n_au_payroll_create_proxy_user(self):
        """ This method will create a new proxy user for the current company based on the selected mode, if no users already exists. """
        self.ensure_one()
        self.env['account_edi_proxy_client.user']._register_proxy_user(self, 'l10n_au_payroll', self.l10n_au_payroll_mode)

    def _l10n_au_payroll_get_proxy_user(self, catch_errors=False):
        """ This method will return the proxy user for the current company based on the selected mode. """
        self.ensure_one()
        if (not self.l10n_au_payroll_proxy_user_id
            and (proxy := self.l10n_au_employer_registration_ids.filtered_domain([("status", "in", ["registered"])]))
            and proxy.status != self.l10n_au_payroll_mode):
            error_msg = _("The payroll mode has changed to %(payroll_mode)s, please register the payroll for %(payroll_mode)s mode. "
                          "Make sure this is a %(payroll_mode)s database before proceeding with %(payroll_mode)s mode.",
                          payroll_mode=self.l10n_au_payroll_mode)
            if catch_errors:
                _logger.error(error_msg)
                return False
            raise UserError(error_msg)
        return self.l10n_au_payroll_proxy_user_id

    def register_payroll(self):
        if self.l10n_au_employer_registration_id.status != "registered":
            raise UserError(_("No employer registration found for this company. "
                              "Please use the payroll onboarding wizard to register your company."))
        if not self.env["l10n_au.super.fund"].search([("is_valid", "=", True)], limit=1):
            self.env["l10n_au.super.fund"]._update_active_funds()
        # Create a proxy user if it does not exist.
        if not self.l10n_au_payroll_proxy_user_id:
            self.env['account_edi_proxy_client.user']._l10n_au_register_proxy_user(
                self,
                self.l10n_au_payroll_mode,
                self.l10n_au_employer_registration_id._prepare_employer_registration()
            )
        # Update the payroll registration of the proxy user if already exists
        else:
            response = self._l10n_au_payroll_get_proxy_user()._l10n_au_payroll_request(
                "/register",
                {
                    "registration_details": self.l10n_au_employer_registration_id._prepare_employer_registration()
                }
            )
            self.l10n_au_bms_id = response.get("client_bms_id")
        for employee in self.env["hr.employee"].search([("company_id", "=", self.id), ("l10n_au_payroll_id", "=", False)]):
            employee.l10n_au_payroll_id = employee._l10n_au_generate_payroll_id(
                employee.name,
                employee.l10n_au_tfn,
                self.vat
            )

    def action_check_abn(self):
        self.ensure_one()
        response = self._l10n_au_make_public_request("/verify_abn", {"abn": self.vat, "legal_name": self.name})
        if response.get("success", False):
            self.l10n_au_abn_valid = True
        elif "error" in response:
            raise ValidationError(response["error"])
        else:
            raise ValidationError(_("Unable to verify this ABN. Please contact your system administrator."))

    def action_view_payroll_onboarding(self):
        self.ensure_one()
        registration = self.l10n_au_employer_registration_ids.filtered(
            lambda r: r.status == "pending"
        )
        if not registration:
            registration = self.env["l10n_au.employer.registration"].sudo().create({
                "company_id": self.id,
                "status": "pending",
            })
        wizard = self.env["l10n_au.payroll.register.wizard"].create({
            "registration_id": registration.id,
        })
        return {
            "name": "Payroll Onboarding",
            "view_mode": "form",
            "res_model": "l10n_au.payroll.register.wizard",
            "view_id": self.env.ref("l10n_au_hr_payroll_api.l10n_au_payroll_register_wizard_form_view").id,
            "res_id": wizard.id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    # --------------------------------
    # Audit Logging Mixin methods
    # --------------------------------
    def _get_audit_logging_fields(self):
        return ["name", "vat", "l10n_au_hr_super_responsible_id", "l10n_au_stp_responsible_id", "l10n_au_bms_id"]
