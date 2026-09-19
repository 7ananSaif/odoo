# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    def _get_offer_values(self):
        self.ensure_one()
        vals = super()._get_offer_values()
        contract_template = self._get_contract_template()
        if contract_template:
            monthly_wage = contract_template.sudo()._get_gross_from_employer_costs(vals['final_yearly_costs'])
            vals.update({
                'monthly_wage': monthly_wage
            })
        return vals
