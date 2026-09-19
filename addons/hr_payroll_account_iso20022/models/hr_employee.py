# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import ValidationError
from odoo.addons.base_iban.models.res_partner_bank import validate_iban


def _is_iban_valid(iban):
    if iban is None:
        return False
    try:
        validate_iban(iban)
        return True
    except ValidationError:
        pass
    return False


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_invalid_iban_employee_ids(self, employees_data=False):
        if not employees_data:
            employees_data = self._get_account_holder_employees_data()
        return [employee['id'] for employee in employees_data if not _is_iban_valid(employee['acc_number'])]
