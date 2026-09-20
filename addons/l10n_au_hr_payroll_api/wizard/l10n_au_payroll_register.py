# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, RedirectWarning


class L10n_AuPayrollRegister(models.TransientModel):
    _name = "l10n_au.payroll.register.wizard"
    _description = "Payroll Onboarding"

    # Stored Fields
    company_id = fields.Many2one(related="registration_id.company_id")
    registration_id = fields.Many2one("l10n_au.employer.registration", string="Registration ID")
    payroll_responsible_id = fields.Many2one(
        "hr.employee",
        required=True,
        default=None,
        compute="_compute_payroll_fields",
        domain="[('user_id', '!=', False)]",
        inverse="_inverse_payroll_responsible",
    )
    registration_fields = fields.Json(depends=["registration_id"], related="registration_id.registration_fields", readonly=False)
    documents_to_sign = fields.Json()

    # Non-stored Fields (used for view)
    stage = fields.Selection(
        selection=[
            ("responsible", "Payroll Responsible"),
            ("authorised", "Authorised"),
            ("company", "Employer Details"),
            ("bank", "Bank Details"),
            ("sign_docs", "Signature"),
        ],
        compute="_compute_payroll_fields",
        inverse="_inverse_stage"
    )
    authorised = fields.Selection(
        selection=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        string="Are you authorised to register for this service on behalf of your employer?",
        compute="_compute_payroll_fields",
        inverse="_inverse_authorised",
        store=False)

    abn = fields.Char(related="company_id.vat", string="ABN")
    company_name = fields.Char(related="company_id.name", string="Registered Business Name")
    trading_name = fields.Char("Trading Business Name", related="company_id.l10n_au_trading_name", readonly=True)
    street = fields.Char(related="company_id.street")
    street2 = fields.Char(related="company_id.street2")
    city = fields.Char(related="company_id.city")
    state_id = fields.Many2one(related="company_id.state_id")
    zip = fields.Char(related="company_id.zip")
    country_id = fields.Many2one(related="company_id.country_id")
    phone = fields.Char(related="company_id.phone")
    payroll_mode = fields.Selection(related="company_id.l10n_au_payroll_mode", string="Payroll Mode", readonly=True)

    payroll_responsible_email = fields.Char(related="payroll_responsible_id.work_email")
    payroll_responsible_position = fields.Char(related="payroll_responsible_id.job_title")
    payroll_responsible_phone = fields.Char(related="payroll_responsible_id.work_phone")

    journal_id = fields.Many2one(string="Bank Journal", comodel_name="account.journal", inverse="_inverse_journal_id")
    bank_name = fields.Char(related="journal_id.bank_id.name", string="Bank Name", readonly=True)
    bank_account_name = fields.Char(related="journal_id.company_partner_id.name", string="Account Name", readonly=True)
    bank_account_number = fields.Char(related="journal_id.bank_acc_number", string="Bank Account Number", readonly=True)
    bank_account_bsb = fields.Char(related="journal_id.aba_bsb", string="BSB", readonly=True)

    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Attachments",
        compute="_compute_attachment_ids",
        help="Attachments provided by the user to support the registration.",
    )
    odoo_disclaimer_check = fields.Boolean(string="I have read and signed Odoo Terms and Conditions provided")
    superchoice_dda_check = fields.Boolean(string="I have read and signed Super Choice FSG PDS DDA provided")

    # -------------------------------------------------------------------------
    # Computes and Inverses
    # The data is stored in registration_fields on l10n_au.employer.registration
    # -------------------------------------------------------------------------

    def write(self, vals):
        if "registration_fields" in vals:
            return super(__class__, self.sudo()).write(vals)
        return super().write(vals)

    @api.depends("registration_id", "company_id", "registration_fields")
    def _compute_payroll_fields(self):
        """Compute the payroll fields based on the current stage."""
        fields = self._fields.keys()
        for record in self:
            record.update({
                field: value
                for field, value in record.registration_fields.items() if field in fields
            })

    def _compute_attachment_ids(self):
        self.update({
            "attachment_ids": self.env.ref("l10n_au_hr_payroll_api.l10n_au_payroll_odoo_disclaimer") | self.env.ref("l10n_au_hr_payroll_api.l10n_au_payroll_superchoice_dda"),
        })

    def _inverse_stage(self):
        """Inverse function for stage field."""
        for record in self:
            record.registration_fields = {
                **record.registration_fields,
                "stage": record.stage,
            }

    def _inverse_payroll_responsible(self):
        """Inverse function for payroll_responsible field."""
        for record in self:
            record.registration_fields = {
                **record.registration_fields,
                "payroll_responsible_id": record.payroll_responsible_id.id,
            }

    def _inverse_authorised(self):
        for record in self:
            record.registration_fields = {
                **record.registration_fields,
                "authorised": record.authorised,
            }

    def _inverse_journal_id(self):
        for record in self:
            record.registration_fields = {
                **record.registration_fields,
                "journal_id": record.journal_id.id,
            }

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_next(self):
        """Action to move to the next stage. And rerenders the wizard."""
        self.ensure_one()
        if self.stage == "responsible":
            if self.payroll_responsible_id and not (self.payroll_responsible_email and self.payroll_responsible_phone):
                raise ValidationError(_("Please set the work email address and work phone for the payroll responsible."))
            self.stage = "authorised"
        elif self.stage == "authorised":
            if self.authorised == "no":
                raise ValidationError(_("You need to be authorised to register for this service on behalf of your employer."))
            self.stage = "company"
        elif self.stage == "company":
            self.stage = "bank"
        elif self.stage == "bank":
            bank_account = self.journal_id.bank_account_id
            if not bank_account:
                raise RedirectWarning(
                            message=_("The bank account on journal '%s' is not set. Please create a new account or set an existing one.", self.journal_id.name),
                            action=self.journal_id._get_records_action(name=_("Configure Journal"), target="new"),
                            button_text=_("Configure Journal Bank Account")
                        )
            if not bank_account.aba_bsb or not bank_account.bank_id:
                raise RedirectWarning(
                    message=_("The account %(account_number)s, of journal '%(journal_name)s', is not valid.\n"
                    "Either its account number is incorrect or it has no BSB or Bank set.",
                    account_number=bank_account.acc_number, journal_name=self.journal_id.name),
                    action=bank_account._get_records_action(name=_("Configure Account"), target="new"),
                    button_text=_("Configure Account")
                )
            # Check stage
            self.stage = "sign_docs"
        else:
            self._register_payroll()
            return self.env.ref("l10n_au_hr_payroll_account.action_open_transfer_previous_payroll")._get_action_dict()
        return self._keep_open()

    def action_back(self):
        """Action to move to the next stage."""
        self.ensure_one()
        if self.stage == "authorised":
            self.stage = "responsible"
        elif self.stage == "company":
            self.stage = "authorised"
        elif self.stage == "bank":
            self.stage = "company"
        elif self.stage == "sign_docs":
            self.stage = "bank"
        return self._keep_open()

    def _keep_open(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'target': 'new',
            'context': dict(self.env.context),
            'views': [(False, 'form')],
            'res_id': self.id,
        }

    def _register_payroll(self):
        """Register the payroll with the ATO."""
        self.ensure_one()
        if self.stage != "sign_docs":
            raise ValidationError(_("Nice Try! You need to complete all the steps before registering."))

        if not (self.odoo_disclaimer_check and self.superchoice_dda_check):
            raise ValidationError(_("Nice Try! You need to agree to both the documents provided. "
                                    "Please review the documents and sign before proceeding."))
        self.registration_fields = {
            **self.registration_fields,
            "payroll_responsible_name": self.payroll_responsible_id.name,
            "payroll_responsible_email": self.payroll_responsible_email,
            "payroll_responsible_phone": self.payroll_responsible_phone,
            "payroll_responsible_position": self.payroll_responsible_position,
            "bank_name": self.bank_name,
            "bank_account_name": self.bank_account_name,
            "bank_account_number": self.bank_account_number,
            "bank_account_bsb": self.bank_account_bsb,
            "abn": self.company_id.vat,
            "company_name": self.company_id.name,
            "trading_name": self.trading_name,
            "street": self.company_id.street,
            "street2": self.company_id.street2,
            "city": self.company_id.city,
            "state_id": self.company_id.state_id.id,
            "zip": self.company_id.zip,
            "country_id": self.company_id.country_id.id,
            "phone": self.company_id.phone,
            "odoo_disclaimer_check": self.odoo_disclaimer_check,
            "superchoice_dda_check": self.superchoice_dda_check,
        }
        self.registration_id.action_confirm(
            registration_mode=self.payroll_mode,
        )

        self.company_id.register_payroll()
        self.company_id.write({
            "l10n_au_stp_responsible_id": self.payroll_responsible_id.id,
            "l10n_au_hr_super_responsible_id": self.payroll_responsible_id.id,
        })
