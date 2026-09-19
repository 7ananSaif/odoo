# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    amount = fields.Float(compute="_compute_amount", readonly=False, store=True)
    l10n_au_is_default_allowance = fields.Boolean()  # True if line is added as a default structure allowance
    l10n_au_payroll_code = fields.Selection(related='input_type_id.l10n_au_payroll_code')
    l10n_au_payroll_code_description = fields.Selection(related='input_type_id.l10n_au_payroll_code_description')
    l10n_au_payment_type = fields.Selection(related='input_type_id.l10n_au_payment_type')
    l10n_au_treatment = fields.Selection(
        string="Treatment",
        selection=[
            ("normal", "Normal"),
            ("backpay", "Backpay"),
            ("salary_sacrifice", "Salary Sacrifice: Other"),
            ("salary_sacrifice_super", "Salary Sacrifice: Superannuation")
        ],
        default="normal",
    )
    l10n_au_input_details_id = fields.Many2one(
        comodel_name="l10n_au.hr.input.details",
        compute="_compute_input_details_id",
    )

    @api.depends("input_type_id")
    def _compute_amount(self):
        for inpt in self:
            inpt.amount = inpt.input_type_id.l10n_au_default_amount

    @api.model_create_multi
    def create(self, vals_list):
        inputs = super().create(vals_list)
        loading_ref = self.env.ref("l10n_au_hr_payroll.input_leave_loading_lump")
        loading_ref_inputs = inputs.filtered(lambda i: i.input_type_id == loading_ref and not i.amount)
        leave_loading_lump_sums = self._l10n_au_get_leave_loading_lump_sums(loading_ref_inputs.payslip_id)
        if loading_ref_inputs:
            loading_ref_inputs.amount = leave_loading_lump_sums.get(loading_ref_inputs.payslip_id)

        inputs_to_add = inputs.filtered(
            lambda i: i.input_type_id.l10n_au_requires_details or i.l10n_au_treatment == "backpay"
        )
        if inputs_to_add:
            self.env["l10n_au.hr.input.details"].create([{
                "input_id": input.id,
            } for input in inputs_to_add])
        return inputs

    def write(self, vals):
        res = super().write(vals)
        if "input_type_id" in vals or "l10n_au_treatment" in vals:
            type = self.input_type_id
            if type.l10n_au_requires_details or self.l10n_au_treatment == "backpay":
                if not self.l10n_au_input_details_id:
                    self.env["l10n_au.hr.input.details"].create([{
                        "input_id": input.id,
                    } for input in self if not input.l10n_au_input_details_id])
            else:
                self.l10n_au_input_details_id.sudo().unlink()
        return res

    @api.model
    def _l10n_au_get_leave_loading_lump_sums(self, payslips):
        res = {}
        for payslip in payslips:
            start_year = payslip.version_id._l10n_au_get_financial_year_start(fields.Date.today())
            employee_allocations = self.env["hr.leave.allocation"].search_read([
                ("employee_id", "=", payslip.employee_id.id),
                ("date_from", ">=", start_year),
                ("holiday_status_id", "in", payslip.version_id.l10n_au_leave_loading_leave_types.ids),
                ("date_from", "<=", payslip.version_id.contract_date_end or payslip.date_to),
            ], ["number_of_days_display"])
            year_expected_leaves = sum(allocation['number_of_days_display'] for allocation in employee_allocations)
            leave_rate = payslip.version_id.l10n_au_leave_loading_rate
            usual_daily_wage = round(payslip._get_daily_wage(), 2)
            res[payslip.id] = year_expected_leaves * (usual_daily_wage * (1 + leave_rate / 100))
        return res

    @api.depends("input_type_id", "l10n_au_treatment")
    def _compute_input_details_id(self):
        for record in self:
            record.l10n_au_input_details_id = record.payslip_id.l10n_au_other_input_details_ids.filtered(lambda x: x.input_id == record)
