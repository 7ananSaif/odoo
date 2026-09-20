# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    wage_with_holidays = fields.Monetary(readonly=False, related="version_id.wage_with_holidays", inherited=True, groups="hr.group_hr_manager")
    wage_on_signature = fields.Monetary(readonly=False, related="version_id.wage_on_signature", inherited=True, groups="hr.group_hr_manager")
    final_yearly_costs = fields.Monetary(readonly=False, related="version_id.final_yearly_costs", inherited=True, groups="hr.group_hr_manager")
    monthly_yearly_costs = fields.Monetary(related="version_id.monthly_yearly_costs", inherited=True, groups="hr.group_hr_manager")

    @api.onchange("wage_with_holidays")
    def _onchange_wage_with_holidays(self):
        self.version_id._onchange_wage_with_holidays()

    @api.onchange('final_yearly_costs')
    def _onchange_final_yearly_costs(self):
        self.version_id._onchange_final_yearly_costs()

    def action_show_contract_reviews(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.version",
            "views": [[False, "list"], [False, "form"]],
            "domain": [["origin_version_id", "=", self.version_id.id]],
            "context": {"active_test": False},
            "name": "Contracts Reviews",
        }

    def action_show_offers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_contract_salary.hr_contract_salary_offer_action')
        action['domain'] = [('employee_id', 'in', self.id)]
        action['context'] = {
            'default_employee_id': self.id,
            'default_employee_version_id': self.version_id.id,
        }
        return action

    def action_generate_offer(self):

        offer_validity_period = int(self.env['ir.config_parameter'].sudo().get_param(
            'hr_contract_salary.employee_salary_simulator_link_validity', default=30))
        offer_values = self._get_offer_values()
        offer_values['default_validity_days_count'] = offer_validity_period

        action = self.env['ir.actions.act_window']._for_xml_id('hr_contract_salary.action_hr_offer_new')
        action['domain'] = [('employee_id', 'in', self.id)]
        action['context'] = {
            'active_model': 'hr.version',
            'default_employee_version_id': self.version_id.id,
            'default_employee_id': self.id,
            'is_simulation_offer': True,
            **offer_values
        }
        return action

    def _get_offer_values(self):
        self.ensure_one()
        return {
            'default_company_id': self.company_id.id,
            'default_contract_template_id': self.version_id.id,
            'default_employee_version_id': self.version_id.id,
            'default_final_yearly_costs': self.final_yearly_costs,
            'default_job_title': self.job_id.name,
            'default_employee_job_id':  self.job_id.id,
            'default_department_id': self.department_id.id,
            'default_display_name': _("Offer for %(recipient)s", recipient=self.name),
        }
