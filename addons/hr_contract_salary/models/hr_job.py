# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrJob(models.Model):
    _inherit = 'hr.job'

    contract_template_id = fields.Many2one('hr.version', domain="[('company_id', '=', company_id), ('employee_id', '=', False)]", string="Contract Template",
        groups="hr.group_hr_user",
        help="Default contract used to generate an offer. If empty, benefits will be taken from current contract of the employee/nothing for an applicant.")

    @api.constrains('contract_template_id', 'company_id')
    def _check_contract_template_company(self):
        for job in self:
            if job.contract_template_id and job.company_id and job.contract_template_id.company_id != job.company_id:
                raise ValidationError(self.env._("The contract template's company must match the job's company."))
