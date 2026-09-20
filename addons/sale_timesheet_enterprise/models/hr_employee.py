# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    billable_time_target = fields.Float("Billing Time Target", groups="hr_timesheet.group_hr_timesheet_user")
    show_billable_time_target = fields.Boolean(related="company_id.timesheet_show_rates")

    @api.model
    def get_all_billable_time_targets(self):
        if self.env.user.has_group("hr_timesheet.group_hr_timesheet_user") and self.env.company.timesheet_show_rates:
            return self.sudo().search_read([("company_id", "=", self.env.company.id)], ["billable_time_target"])
        return []

    _check_billable_time_target = models.Constraint(
        'CHECK(billable_time_target >= 0)',
        "The billable time target cannot be negative.",
    )


class HREmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    billable_time_target = fields.Float(compute='_compute_billable_time_target')
    show_billable_time_target = fields.Boolean(compute='_compute_billable_time_target')

    def _compute_billable_time_target(self):
        self._compute_from_employee('billable_time_target')
        self._compute_from_employee('show_billable_time_target')
