from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    car_atn = fields.Float(related="version_id.car_atn", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    wishlist_car_total_depreciated_cost = fields.Float(related="version_id.wishlist_car_total_depreciated_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    company_car_total_depreciated_cost = fields.Float(related="version_id.company_car_total_depreciated_cost", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.onchange('new_bike')
    def _onchange_new_bike(self):
        self.version_id._onchange_new_bike()

    @api.onchange('has_bicycle')
    def _onchange_has_bicycle(self):
        self.version_id._onchange_has_bicycle()
