# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.http import request

from odoo.addons.hr_contract_salary.controllers import main
from odoo.addons.sign.controllers.main import Sign

class SignContract(Sign):

    def _update_version_on_signature(self, request_item, version, offer):
        result = super()._update_version_on_signature(request_item, version, offer)
        if request_item.sign_request_id.nb_wait == 0 and not version.leave_allocation_id:
            auto_allocation = version.company_id.hr_contract_timeoff_auto_allocation
            if auto_allocation and version.holidays:
                time_off_type = version.company_id.hr_contract_timeoff_auto_allocation_type_id
                # Sudo is required here because it isn't guaranteed that the second person signing will be a manager.
                records = request.env['hr.leave.allocation'].sudo().create({
                    'name': time_off_type.name,
                    'employee_id': version.employee_id.id,
                    'number_of_days': version.holidays,
                    'holiday_status_id': time_off_type.id,
                    'state': 'confirm',
                    'notes': _('Allocation automatically created from Contract Signature.'),
                })
                version.leave_allocation_id = records[0]
                version.leave_allocation_id.action_approve()
        return result
