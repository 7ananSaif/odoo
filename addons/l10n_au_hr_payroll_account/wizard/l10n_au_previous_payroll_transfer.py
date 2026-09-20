# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models, _
from odoo.addons.l10n_au_hr_payroll.models.hr_version import INCOME_STREAM_TYPES


class L10n_AuPreviousPayrollTransfer(models.TransientModel):
    _name = 'l10n_au.previous.payroll.transfer'
    _description = "Transfer From Previous Payroll System"

    def _default_fiscal_year_start_date(self):
        return self.env["l10n_au.payslip.ytd"]._get_start_date(fields.Date.today())

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, domain=[("country_code", "=", "AU")])
    previous_bms_id = fields.Char(string="Previous BMS ID", required=False,
                                  default=lambda self: self.env.company.l10n_au_previous_bms_id,
                                  help="Enter the ID of the employee in the previous payroll system.")
    l10n_au_previous_payroll_transfer_employee_ids = fields.One2many("l10n_au.previous.payroll.transfer.employee", "l10n_au_previous_payroll_transfer_id", store=True, readonly=False, compute="_compute_all_employees")
    fiscal_year_start_date = fields.Date(
        string="Fiscal Year Start Date",
        required=True,
        default=_default_fiscal_year_start_date
    )

    def write(self, vals):
        if "fiscal_year_start_date" in vals:
            vals["fiscal_year_start_date"] = self.env["l10n_au.payslip.ytd"]._get_start_date(vals["fiscal_year_start_date"])
        return super().write(vals)

    @api.depends("company_id")
    def _compute_all_employees(self):
        for rec in self:
            if not rec.company_id:
                continue
            employees_to_add = (
                rec.env["hr.employee"]
                .with_context(active_test=False)
                .search(
                    [
                        ("id", "not in", rec.l10n_au_previous_payroll_transfer_employee_ids.employee_id.ids),
                        ("company_id", "=", rec.company_id.id),
                        ("version_id", "!=", False)
                    ]
                )
            )
            employees_to_remove = rec.l10n_au_previous_payroll_transfer_employee_ids.filtered(lambda x: x.employee_id.company_id != rec.company_id)
            rec.update(
                {
                    "l10n_au_previous_payroll_transfer_employee_ids": [
                        Command.create({"employee_id": emp.id, "previous_payroll_id": emp.l10n_au_previous_payroll_id})
                        for emp in employees_to_add
                    ] + [Command.unlink(emp.id) for emp in employees_to_remove]
                }
            )

    def action_transfer(self):
        self.ensure_one()
        is_current_year = self._default_fiscal_year_start_date() == self.fiscal_year_start_date
        self.company_id.write({"l10n_au_previous_bms_id": self.previous_bms_id})
        for rec in self.l10n_au_previous_payroll_transfer_employee_ids:
            rec.employee_id.l10n_au_previous_payroll_id = rec.previous_payroll_id

        created_ytd = self.company_id._create_ytd_values(
            self.l10n_au_previous_payroll_transfer_employee_ids.employee_id, self.fiscal_year_start_date)

        if created_ytd and is_current_year:
            # Create update event with previous_payroll_id and bms_id for the current fiscal year
            self.env["l10n_au.stp"].create(
                {
                    "company_id": self.company_id.id,
                    "payevent_type": "update",
                    "start_date": self.fiscal_year_start_date,
                    "is_opening_balances": True,
                    "l10n_au_stp_emp": [
                        Command.create({
                            "employee_id": emp.id,
                        }) for emp in self.l10n_au_previous_payroll_transfer_employee_ids.employee_id
                    ]
                }
            )
            return created_ytd.with_context(search_default_filter_group_employee_id=1, search_default_filter_group_income_stream=1)\
                ._get_records_action(name=_("Opening Balances"))
        return {"type": "ir.actions.act_window_close"}


class L10n_AuPreviousPayrollTransferEmployee(models.TransientModel):
    _name = 'l10n_au.previous.payroll.transfer.employee'
    _description = "Employee Transfer From Previous Payroll System"

    l10n_au_previous_payroll_transfer_id = fields.Many2one("l10n_au.previous.payroll.transfer", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="l10n_au_previous_payroll_transfer_id.company_id")
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    previous_payroll_id = fields.Char(
        "Previous Payroll ID",
        compute="_compute_payroll_id",
        required=True, store=True, readonly=False,
    )
    l10n_au_income_stream_type = fields.Selection(
        selection=INCOME_STREAM_TYPES,
        string="Income Stream Type",
        compute="_compute_income_stream_type",
        required=True, store=True, readonly=False
    )

    _unique_employee_transfer = models.Constraint(
        'unique(employee_id, l10n_au_previous_payroll_transfer_id, l10n_au_income_stream_type)',
        "An employee can only be transferred once per Income Stream Type.",
    )

    @api.depends("employee_id")
    def _compute_payroll_id(self):
        for rec in self:
            rec.previous_payroll_id = rec.employee_id.l10n_au_previous_payroll_id

    @api.depends("employee_id")
    def _compute_income_stream_type(self):
        for rec in self:
            rec.l10n_au_income_stream_type = rec.employee_id.l10n_au_income_stream_type
