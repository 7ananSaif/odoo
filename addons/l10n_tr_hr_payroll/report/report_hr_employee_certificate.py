from odoo import api, models
from odoo.exceptions import UserError


class ReportHrEmploymentCertificate(models.AbstractModel):
    _name = 'report.l10n_tr_hr_payroll.report_emp_employement_cert'
    _description = 'Employment Certificate Report'

    @api.model
    def _get_report_values(self, docids, data={}):
        # for studio
        if data.get('studio', False):
            return {'doc_ids': docids}

        if not self.env.user.phone:
            raise UserError(self.env._("Cannot generate report. Missing:\n- Logged User's Phone"))
        employees = self.env['hr.employee'].browse(docids)
        error_message = []
        for emp in employees:
            missing = self._get_missing_fields(emp)
            if missing:
                error_message.append(
                    self.env._("Cannot generate report for %(name)s. Missing:\n- %(fields)s") % {
                        'name': emp.name,
                        'fields': "\n- ".join(missing)
                    }
                )
        if error_message:
            raise UserError('\n\n'.join(error_message))

        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': employees,
        }

    def _get_missing_fields(self, emp):
        missing = []
        fields = emp._fields

        # Common required fields
        required_fields = ['name']

        # Conditional based on citizenship
        if emp.l10n_tr_is_current_turkey_citizen:
            required_fields += ['identification_id']
        else:
            required_fields += ['country_id', 'permit_no', 'work_permit_expiration_date']

        # Check each required field
        for field_name in required_fields:
            if not emp[field_name]:
                label = fields[field_name].string
                missing.append(label)
        return missing
