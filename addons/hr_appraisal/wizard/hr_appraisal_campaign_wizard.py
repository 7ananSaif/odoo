from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.fields import Domain


class HrAppraisalCampaignWizard(models.TransientModel):

    _name = 'hr.appraisal.campaign.wizard'
    _description = 'Appraisal Campaign Wizard'
    _inherit = ['hr.mixin']

    mode = fields.Selection([
        ('employee', 'By Employee'),
        ('company', 'By Company'),
        ('department', 'By Department'),
        ('category', 'By Employee Tag')],
        string='Mode', default='employee', required=True,
        help="Allow to create appraisals in batches:\n- By Employee: for specific employees"
        "\n- By Company: all employees of the specified company"
        "\n- By Department: all employees of the specified department"
        "\n- By Employee Tag: all employees of the specific employee group category")
    employee_ids = fields.Many2many("hr.employee", string="Employees", relation="employees", domain=lambda self: self._employees_domain())
    department_id = fields.Many2one("hr.department", string="Department")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    category_id = fields.Many2one('hr.employee.category', string='Employee Tag')
    manager = fields.Selection([
        ('employee_manager', "Employee's Manager"),
        ('person', 'Other'),
        ], string='Manager', default='employee_manager',
        help="'Employee's Manager': Each appraisal will be conducted by the direct manager of the employee"
        "\n'Specific Person': All appraisals will be conducted by the specified employees")
    manager_ids = fields.Many2many("hr.employee", string="Managers", relation="managers")
    appraisal_template_id = fields.Many2one('hr.appraisal.template', string="Appraisal Template", required=True,
        domain=[('company_id', 'in', [company_id, False])])
    appraisal_date = fields.Date(default=fields.Date.today() + relativedelta(months=1), required=True)
    warning = fields.Char(compute="_compute_warning")

    def _employees_domain(self):
        user = self.env.user
        domain = Domain([('company_id', 'in', self.env.companies.ids)])
        if not user.has_group('hr_appraisal.group_hr_appraisal_user'):
            domain &= Domain([('id', 'child_of', user.employee_id.id)])
        return domain

    @api.depends('mode', 'manager', 'manager_ids', 'employee_ids', 'company_id', 'department_id', 'category_id', 'appraisal_date')
    def _compute_warning(self):
        warnings = []
        employees = self._get_employees_from_mode()

        if not employees:

            if self.mode == 'company' and self.company_id:
                warnings.append(self.env._("The company %(company_name)s doesn't have employees", company_name=self.company_id.name))

            elif self.mode == 'department' and self.department_id:
                warnings.append(self.env._("The department %(department_name)s doesn't have employees", department_name=self.department_id.name))

            elif self.mode == 'category' and self.category_id:
                warnings.append(self.env._("No employees have the tag %(category_name)s", category_name=self.category_id.name))

        if self.manager == 'employee_manager':
            employees_without_managers = employees.filtered(lambda emp: not emp.parent_id or emp.parent_id == emp._origin)
            if employees_without_managers:
                warning_message = self.env._("Appraisals won't be created for the following employees because they don't have a manager: %(employees)s", employees=', '.join(employees_without_managers.mapped('name')))
                warnings.append(warning_message)

        similar_appraisals = self._get_appraisals_with_same_date_and_managers(employees)
        if similar_appraisals:
            warning_message = self.env._("The following employees already have appraisals on %(appraisal_date)s: %(employees)s. The existing appraisals will be used instead of creating new ones.", appraisal_date=self.appraisal_date, employees=', '.join(similar_appraisals.mapped('employee_id.name')))
            warnings.append(warning_message)

        self.warning = '\n'.join(['- ' + warning for warning in warnings])

    def _get_appraisals_with_same_date_and_managers(self, employees):
        similar_appraisals = self.env['hr.appraisal']
        managers = self.manager_ids.ids if self.manager == 'person' else employees.mapped('parent_id.id')
        for employee in employees:
            if self.manager == 'person':
                managers = self.manager_ids.filtered(lambda m: m.id != employee.id)
            else:
                managers = employee.parent_id if employee.parent_id != employee else False

            similar_appraisals |= employee.sudo().mapped('appraisal_ids').filtered(lambda a:
                a.date_close == self.appraisal_date and
                managers and
                set(managers.ids).issubset(a.manager_ids.ids)
            ).sudo(False)
        return similar_appraisals

    def action_generate_appraisals(self):
        employees = self._get_employees_from_mode()
        appraisals = self._create_employees_appraisals(employees)
        action = self.env['ir.actions.act_window']._for_xml_id('hr_appraisal.hr_appraisal_action_multiple_appraisals')
        action["domain"] = [('id', 'in', appraisals.ids)]
        action["context"] = self.env.context
        return action

    def _get_employees_from_mode(self):
        if self.mode == 'employee':
            employees = self.employee_ids or self.env['hr.employee'].search([('company_id', 'in', self.env.companies.ids)])
        elif self.mode == 'company':
            employees = self.env['hr.employee'].search([('company_id', '=', self.company_id.id)])
        elif self.mode == 'category':
            employees = self.category_id.employee_ids.filtered(lambda e: e.company_id in self.env.companies)
        else:
            employees = self.department_id.member_ids
        return employees

    def _create_employees_appraisals(self, employees):
        similar_appraisals = self._get_appraisals_with_same_date_and_managers(employees)
        employees_without_appraisal = employees - similar_appraisals.employee_id
        create_vals = []
        for employee in employees_without_appraisal:
            if self.manager == 'person':
                managers = self.manager_ids.filtered(lambda m: m.id != employee.id)
            else:
                managers = employee.parent_id if employee.parent_id != employee else False
            # A warning will be generated in compute_warning about employees without a direct manager.
            if managers:
                create_vals.append({
                    'employee_id': employee.id,
                    'manager_ids': managers,
                    'date_close': self.appraisal_date,
                    'appraisal_template_id': self.appraisal_template_id.id,
                    'state': '2_pending',
                    'employee_feedback_published': False,
                    'manager_feedback_published': False,
                })

        return similar_appraisals + self.env['hr.appraisal'].create(create_vals)
