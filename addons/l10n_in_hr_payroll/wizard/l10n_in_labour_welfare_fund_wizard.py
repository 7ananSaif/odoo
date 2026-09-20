from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models


class L10nInLabourWelfareFundWizard(models.TransientModel):
    _name = 'l10n.in.labour.welfare.fund.wizard'
    _description = 'Labour Welfare Fund'

    date_from = fields.Date(default=lambda self: fields.Date.today() + relativedelta(day=1, month=1))
    date_to = fields.Date(default=lambda self: fields.Date.today() + relativedelta(day=31, month=12))
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    department_id = fields.Many2one('hr.department', string='Department', domain="[('company_id', '=', company_id)]")
    line_ids = fields.One2many(
        'l10n.in.labour.welfare.fund.line.wizard', 'wizard_id',
        compute='_compute_line_ids', store=True, readonly=False)

    @api.depends('department_id')
    def _compute_line_ids(self):
        for wizard in self:
            if not wizard.department_id:
                member_ids = self.env['hr.employee'].search([('company_id', '=', wizard.company_id.id)])
            else:
                member_ids = wizard.department_id.member_ids

            wizard.line_ids = [Command.clear()]
            for employee in member_ids:
                wizard.line_ids = [(0, 0, {
                    'employee_id': employee.id,
                    'wizard_id': wizard.id,
                })]

    def action_export_xls(self):
        self.ensure_one()
        return {
            'name': 'Export Group Insurance Amount',
            'type': 'ir.actions.act_url',
            'url': '/export/labour_welfare_fund/%s' % (self.id),
        }


class L10nInLabourWelfareFundLineWizard(models.TransientModel):
    _name = 'l10n.in.labour.welfare.fund.line.wizard'
    _description = 'Labour Welfare Fund Line'

    wizard_id = fields.Many2one('l10n.in.labour.welfare.fund.wizard')
    employee_id = fields.Many2one('hr.employee', required=True)
    employee_lwf_account = fields.Char(related="employee_id.l10n_in_lwf_account_number", string='Employee LWF Account')
    employee_name = fields.Char(related='employee_id.name', string='Employee Name')
    employee_contibution = fields.Float(string='Employee Contribution')
    employer_contribution = fields.Float(string='Employer Contribution')
    total_contribution = fields.Float(string='Total Contribution')

    def create(self, vals_list):
        new_vals_list = []
        employee_ids = [val_list.get('employee_id') for val_list in vals_list]
        payslips = self.env['hr.payslip'].search([
                    ('employee_id', 'in', employee_ids),
                    ('state', '=', 'paid'),
                ])
        for val_list in vals_list:
            employee = self.env['hr.employee'].browse(val_list.get('employee_id'))
            wizard = self.env['l10n.in.labour.welfare.fund.wizard'].browse(val_list.get('wizard_id'))
            employee_payslips = payslips.filtered(lambda p: p.employee_id == employee and p.date_from >= wizard.date_from and p.date_to <= wizard.date_to)
            if not employee_payslips:
                continue

            salary_rules = employee_payslips._get_line_values(['LWF', 'LWFE'])
            if not salary_rules:
                continue

            val_list['employee_contibution'] = 0
            val_list['employer_contribution'] = 0
            for rule, vals in salary_rules.items():
                if rule == 'LWFE':
                    val_list['employee_contibution'] += sum(vals[id]['total'] for id in employee_payslips.ids)
                elif rule == 'LWF':
                    val_list['employer_contribution'] += sum(vals[id]['total'] for id in employee_payslips.ids)
            val_list['total_contribution'] = val_list['employee_contibution'] + val_list['employer_contribution']
            new_vals_list.append(val_list)
        return super().create(new_vals_list)
