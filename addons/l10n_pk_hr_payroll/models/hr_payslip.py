# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _l10n_pk_get_tax(self, income):
        self.ensure_one()
        result = 0
        tax_brackets = iter(self._rule_parameter('l10n_pk_tax_brackets'))
        for low, high, rate, fix in tax_brackets:
            if income > low:
                if income <= high:
                    result += rate * (income - low)
                    break
                else:
                    result += fix
        return result
