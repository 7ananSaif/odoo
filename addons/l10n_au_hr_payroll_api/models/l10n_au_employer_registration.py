# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class EmployerRegistration(models.Model):
    _name = "l10n_au.employer.registration"
    _description = "Employer Registration"
    _order = "create_date"
    _inherit = ['mail.thread']

    company_id = fields.Many2one(
        "res.company", "Company", required=True, default=lambda self: self.env.company
    )
    status = fields.Selection(
        [("pending", "Pending"), ("registered", "Registered"), ("expired", "Expired")],
        string="Status",
        required=True,
        default="pending",
        tracking=True,
    )
    registration_mode = fields.Selection(
        [("test", "Testing"), ("prod", "Production")],
        string="Registration Mode",
        required=True,
        tracking=True,
        default=lambda self: self.env.company.l10n_au_payroll_mode,
    )
    odoo_disclaimer_check = fields.Boolean(
        string="I have read and signed Odoo Terms and Conditions provided",
        compute="_compute_authorisation_checks",
    )
    superchoice_dda_check = fields.Boolean(
        string="I have read and signed Super Choice FSG PDS DDA provided",
        compute="_compute_authorisation_checks",
    )
    # Stored as JSON to allow dynamic fields
    registration_fields = fields.Json()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "registration_fields" not in vals:
                # Default values for registration fields
                vals["registration_fields"] = {
                    "stage": "responsible",
                    "payroll_responsible_id": self.env.user.employee_id.id,
                    "authorised": False,
                    "journal_id": False,
                }
        return super().create(vals_list)

    @api.depends("company_id", "registration_mode")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.company_id.name} ({record.registration_mode})"

    @api.depends("registration_fields")
    def _compute_authorisation_checks(self):
        for record in self:
            record.odoo_disclaimer_check = record.registration_fields.get("odoo_disclaimer_check", False)
            record.superchoice_dda_check = record.registration_fields.get("superchoice_dda_check", False)

    @api.constrains("registration_mode", "status", "registration_fields")
    def _check_registration_mode(self):
        """ Check if the registration is in testing mode """
        for registration in self:
            if registration.status == "registered" and not registration.registration_mode:
                raise ValidationError(_("Registration mode must be set when confirming the registration!"))
            if registration.status == "registered" and not (
                registration.registration_fields.get("odoo_disclaimer_check") and
                registration.registration_fields.get("superchoice_dda_check")
            ):
                raise ValidationError(_("You must accept the Odoo Terms & Conditions and Super Choice DDA to proceed with the registration!"))

    def action_confirm(self, registration_mode):
        """ Confirm the registration and set the status to registered """
        self.ensure_one()
        self.env["l10n_au.employer.registration"].search([
            ("company_id", "=", self.company_id.id),
            ("status", "=", "registered"),
        ]).sudo().status = "expired"
        sudo_self = self.sudo()
        if self.status != "pending":
            raise ValidationError(_("Employer registration is not in a pending state."))
        sudo_self.write({
            "status": "registered",
            "registration_mode": registration_mode,
        })

    def _prepare_employer_registration(self):
        """ Prepare the employer registration data for submission """

        self.ensure_one()
        if self.status != "registered":
            raise ValidationError(_("Employer registration is not in a registered state."))
        return {
            "status": self.status,
            # Company details
            "company_record_id": self.company_id.id,
            "trading_name": self.registration_fields.get("trading_name"),
            "company_name": self.registration_fields.get("company_name"),
            "company_abn": self.registration_fields.get("abn"),
            "company_street": self.registration_fields.get("street"),
            "company_street2": self.registration_fields.get("street2"),
            "company_city": self.registration_fields.get("city"),
            "company_state": self.env["res.country.state"].browse(self.registration_fields.get("state_id")).name,
            "company_zip": self.registration_fields.get("zip"),
            "company_country": self.env["res.country"].browse(self.registration_fields.get("country_id")).name,
            "company_phone": self.registration_fields.get("phone"),
            # Authorized person details
            "payroll_responsible_id": self.registration_fields.get("payroll_responsible_id"),
            "payroll_responsible_name": self.env["hr.employee"].browse(self.registration_fields.get("payroll_responsible_id")).name,
            "payroll_responsible_email": self.registration_fields.get("payroll_responsible_email"),
            "payroll_responsible_phone": self.registration_fields.get("payroll_responsible_phone"),
            "payroll_responsible_position": self.registration_fields.get("payroll_responsible_position"),
            "payroll_responsible_authorised": self.registration_fields.get("authorised"),
            # Bank account details
            "journal_id": self.registration_fields.get("journal_id"),
            "bank_account_name": self.registration_fields.get("bank_account_name"),
            "bank_account_number": self.registration_fields.get("bank_account_number"),
            "bank_account_bsb": self.registration_fields.get("bank_account_bsb"),
            # Authorization details
            "odoo_disclaimer_check": self.registration_fields.get("odoo_disclaimer_check"),
            "superchoice_dda_check": self.registration_fields.get("superchoice_dda_check"),
        }
