# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from ast import literal_eval


class HrSalaryRule(models.Model):
    _name = 'hr.salary.rule'
    _order = 'sequence, id'
    _description = 'Salary Rule'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True,
        help="The code of salary rules can be used as reference in computation of other rules. "
             "In that case, it is case sensitive.")
    struct_id = fields.Many2one('hr.payroll.structure', string="Salary Structure", required=True, index=True, ondelete='cascade')
    country_id = fields.Many2one(related="struct_id.country_id")
    sequence = fields.Integer(required=True, index=True, default=5,
        help='Use to arrange calculation sequence')
    quantity = fields.Char(default='1.0',
        help="It is used in computation for percentage and fixed amount. "
             "E.g. a rule for Meal Voucher having fixed amount of "
             u"1€ per worked day can have its quantity defined in expression "
             "like worked_days['WORK100'].number_of_days.")
    category_id = fields.Many2one('hr.salary.rule.category', string='Category', required=True, domain="['|', ('country_id', '=', False), ('country_id', '=', country_id)]")
    active = fields.Boolean(default=True,
        help="If the active field is set to false, it will allow you to hide the salary rule without removing it.")
    appears_on_payslip = fields.Boolean(string='Appears on Payslip', default=True,
        help="Used to display the salary rule on payslip.")
    appears_on_employee_cost_dashboard = fields.Boolean(string='Contributes to Employer Cost', default=False,
        help="Used to compute the employer cost of a payslip.")
    condition_select = fields.Selection([
        ('none', 'Always True'),
        ('property_input', 'Salary Input'),
        ('input', 'Other Input'),
        ('python', 'Python Expression'),
        ('domain', 'Domain')
    ], string="Condition Based on", default='none', required=True)
    condition_other_input_id = fields.Many2one('hr.payslip.input.type', domain=[('is_quantity', '=', False)])
    condition_python = fields.Text(string='Python Condition', required=True,
        default='''
result = result_rules['NET']['total'] > categories['NET'] * 0.10''',
        help='Applied this rule for calculation if condition is true. You can specify condition like basic > 1000.')
    condition_domain = fields.Char(string='Applicability Domain', help="Define the applicability rules for this rule.")
    amount_select = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fix', 'Fixed Amount'),
        ('input', 'Other Input'),
        ('code', 'Python Code'),
    ], string='Amount Type', index=True, required=True, default='fix', help="The computation method for the rule amount.")
    amount_fix = fields.Float(string='Fixed Amount', digits='Payroll')
    amount_percentage = fields.Float(string='Percentage (%)', digits='Payroll Rate',
        help='For example, enter 50.0 to apply a percentage of 50%')
    amount_other_input_id = fields.Many2one('hr.payslip.input.type', domain=[('is_quantity', '=', False)])
    amount_python_compute = fields.Text(string='Python Code',
        default='''
result = version.wage
result_rate = 10''')
    amount_percentage_base = fields.Char(string='Percentage based on', help='result will be affected to a variable')
    partner_id = fields.Many2one('res.partner', string='Partner',
        help="Eventual third party involved in the salary payment of the employees.")
    note = fields.Html(string='Description', translate=True)
    color = fields.Char('Color', default='#000000')
    title = fields.Boolean(string="Title", help="When selected, this salary rule will only be displayed as a title with its description, without numeric values.")
    bold = fields.Boolean(string="Bold")
    underline = fields.Boolean(string="Underline")
    italic = fields.Boolean(string="Italic")
    indented = fields.Boolean(string="Indented")
    space_above = fields.Boolean(string="Space Above")

    input_usage_employee = fields.Boolean()
    input_usage_payslip = fields.Boolean()
    input_default_value = fields.Float("Default Value")
    input_default_boolean = fields.Boolean("Selected by Default")
    input_description = fields.Char()
    input_section = fields.Many2one('hr.salary.rule.section', string="Section", default=lambda self: self.env.ref('hr_payroll.default_salary_rule_section', raise_if_not_found=False), domain="['|', ('struct_ids', 'in', struct_id), ('struct_ids', '=', False)]")
    input_unit = fields.Selection(string="Unit", selection=[('monetary', 'Monetary'),
                                                            ('quantity', 'Quantity'),
                                                            ('percentage', 'Percentage'),
                                                            ('boolean', 'Checkbox')],
                                  default='monetary')
    input_suffix = fields.Char()
    dependent_input_id = fields.Many2one('hr.salary.rule', string='Dependent Salary Input', domain="[('id', '!=', id), ('struct_id', '=', struct_id), ('dependent_input_id', '=', False), ('condition_select', '=', 'property_input')]")
    input_used_in_definition = fields.Boolean(compute='_compute_input_used_in_definition', search='_search_input_used_in_definition')

    @api.model
    def update_properties_definition_domain(self, salary_rule_ids, res_model):
        grouped_rules = self.browse(salary_rule_ids).grouped('struct_id')
        for struct, rules in grouped_rules.items():
            struct._update_payroll_properties(rules, res_model)

    def _compute_input_used_in_definition(self):
        all_structures = self.grouped('struct_id')
        definitions_inputs_by_structure = defaultdict(set)

        for struct in all_structures:
            definitions_inputs_by_structure[struct] = {
                prop['name'] for prop in struct.payslip_properties_definition if not prop['name'].startswith('separator_')
            } | {
                prop['name'] for prop in struct.version_properties_definition if not prop['name'].startswith('separator_')
            }

        for rule in self:
            rule.input_used_in_definition = rule.condition_select == 'property_input' and str(rule.id) in definitions_inputs_by_structure[rule.struct_id]

    def _search_input_used_in_definition(self, operator, value):
        # operator should be '=' or '!='
        # value is True/False
        if operator not in ('=', '!='):
            raise UserError(self.env._("Unsupported operator %s") % operator)

        # collect all struct->input_names mapping
        all_structures = self.env['hr.payroll.structure'].search([])
        definitions_inputs_by_structure = defaultdict(set)
        for struct in all_structures:
            definitions_inputs_by_structure[struct.id] = {
                prop['name'] for prop in struct.payslip_properties_definition if not prop['name'].startswith('separator_')
            } | {
                prop['name'] for prop in struct.version_properties_definition if not prop['name'].startswith('separator_')
            }

        # find rule ids that match the condition
        matching_rules = []
        rules = self.env['hr.salary.rule'].search([('condition_select', '=', 'property_input')])
        for rule in rules:
            if str(rule.id) in definitions_inputs_by_structure.get(rule.struct_id.id, set()):
                matching_rules.append(rule.id)

        domain = [('id', 'in', matching_rules)]
        if (operator == '=' and not value) or (operator == '!=' and value):
            domain = [('id', 'not in', matching_rules)]

        return domain

    def _raise_error(self, localdict, error_type, e):
        raise UserError(_("""%(error_type)s
- Employee: %(employee)s
- Version: %(version)s
- Payslip: %(payslip)s
- Salary rule: %(name)s (%(code)s)
- Error: %(error_message)s""",
            error_type=error_type,
            employee=localdict['employee'].name,
            version=localdict['version'].name,
            payslip=localdict['payslip'].name,
            name=self.name,
            code=self.code,
            error_message=e))

    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """
        self.ensure_one()
        localdict['localdict'] = localdict

        if self.condition_select == 'property_input':
            if self.id not in localdict['property_inputs']:
                return 0.0, 1.0, 100.0
            return localdict['property_inputs'][self.id], 1.0, 100.0

        if self.amount_select == 'fix':
            try:
                return self.amount_fix or 0.0, float(safe_eval(self.quantity, localdict)), 100.0
            except Exception as e:
                self._raise_error(localdict, _("Wrong quantity defined for:"), e)
        if self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage or 0.0)
            except Exception as e:
                self._raise_error(localdict, _("Wrong percentage base or quantity defined for:"), e)
        if self.amount_select == 'input':
            if self.amount_other_input_id.code not in localdict['inputs']:
                return 0.0, 1.0, 100.0
            return localdict['inputs'][self.amount_other_input_id.code].amount, 1.0, 100.0
        # python code
        try:
            safe_eval(self.amount_python_compute or 0.0, localdict, mode='exec')
            return float(localdict['result']), localdict.get('result_qty', 1.0), localdict.get('result_rate', 100.0)
        except Exception as e:
            self._raise_error(localdict, _("Wrong python code defined for:"), e)

    def _satisfy_condition(self, localdict):
        self.ensure_one()
        localdict['localdict'] = localdict
        if self.condition_select == 'none':
            return True
        if self.condition_select == 'input':
            return self.condition_other_input_id.code in localdict['inputs']
        if self.condition_select == 'domain':
            return localdict['payslip'].filtered_domain(literal_eval(self.condition_domain or '[]'))
        if self.condition_select == 'property_input':
            return self.id in localdict['property_inputs']
        # python code
        try:
            safe_eval(self.condition_python, localdict, mode='exec')
            return localdict.get('result', False)
        except Exception as e:
            self._raise_error(localdict, _("Wrong python condition defined for:"), e)

    def _get_report_field_name(self):
        self.ensure_one()
        return 'x_l10n_%s_%s' % (
            self.struct_id.country_id.code.lower() if self.struct_id.country_id.code else 'xx',
            self.code.lower().replace('.', '_').replace('-', '_').replace(' ', '_'),
        )

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        if default and 'name' in default:
            return vals_list
        return [dict(vals, name=self.env._("%s (copy)", rule.name)) for rule, vals in zip(self, vals_list)]

    @api.constrains('category_id', 'struct_id')
    def _check_category_country(self):
        for rule in self:
            if rule.category_id.country_id and rule.country_id and rule.category_id.country_id != rule.country_id:
                raise ValidationError(_("Rule category and structure should belong to the same country"))
