from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if not any(company.timesheet_show_rates for company in self.env.user.company_ids):
            if self.env.user.has_group('hr_timesheet.group_timesheet_manager') and self.env.user.has_group('base.group_system'):
                res.extend([
                    self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_employee_billable_time_target').id,
                    self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_employee').id,
                    self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_configuration_tips').id,
                ])
            else:
                res.append(self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_configuration_settings').id)
        elif self.env.user.has_group('hr.group_hr_user'):
            res.append(self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_employee_billable_time_target').id)

        return res
