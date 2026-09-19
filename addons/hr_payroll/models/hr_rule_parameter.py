# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tools.safe_eval import safe_eval

from odoo import api, fields, models, _
from odoo.tools import ormcache
from odoo.tools.misc import format_date
from odoo.exceptions import UserError


class HrRuleParameterValue(models.Model):
    _name = 'hr.rule.parameter.value'
    _description = 'Salary Rule Parameter Value'
    _order = 'date_from desc'

    rule_parameter_id = fields.Many2one('hr.rule.parameter', required=True, index=True, ondelete='cascade', default=lambda self: self.env.context.get('active_id'))
    rule_parameter_name = fields.Char(related="rule_parameter_id.name", readonly=True)
    code = fields.Char(related="rule_parameter_id.code", index=True, store=True, readonly=True)
    date_from = fields.Date(string="From", index=True, required=True)
    parameter_value = fields.Text(help="Python data structure")
    country_id = fields.Many2one(related="rule_parameter_id.country_id")

    _unique_parameter = models.Constraint(
        'unique (rule_parameter_id, date_from)',
        "Two rules with the same code cannot start the same day",
    )

    @api.constrains('parameter_value')
    def _check_parameter_value(self):
        for value in self:
            try:
                safe_eval(value.parameter_value)
            except Exception as e:
                raise UserError(_('Wrong rule parameter value for %(rule_parameter_name)s at date %(date)s.\n%(error)s', rule_parameter_name=value.rule_parameter_name, date=format_date(self.env, value.date_from), error=str(e)))

    @api.model_create_multi
    def create(self, vals_list):
        self.env.registry.clear_cache()
        return super().create(vals_list)

    def write(self, vals):
        if 'date_from' in vals or 'parameter_value' in vals:
            self.env.registry.clear_cache()
        return super().write(vals)

    def unlink(self):
        self.env.registry.clear_cache()
        return super().unlink()


class HrRuleParameter(models.Model):
    _name = 'hr.rule.parameter'
    _description = 'Salary Rule Parameter'

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="This code is used in salary rules to refer to this parameter.")
    description = fields.Html()
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.company.country_id)
    parameter_version_ids = fields.One2many('hr.rule.parameter.value', 'rule_parameter_id', string='Versions')
    current_value_one_line = fields.Text(string='Current Value (short)', compute='_compute_current_value')
    valid_since = fields.Date(compute='_compute_current_value')
    salary_rule_ids = fields.One2many('hr.salary.rule', compute='_compute_salary_rule', string='Salary Rules')
    salary_rule_count = fields.Integer(compute='_compute_salary_rule')

    _unique_code = models.Constraint(
        'unique (code)',
        "Two rule parameters cannot have the same code.",
    )

    @api.model
    @ormcache('code', 'date', 'tuple(self.env.context.get("allowed_company_ids", []))')
    def _get_parameter_from_code(self, code, date=None, raise_if_not_found=True):
        if not date:
            date = fields.Date.today()
        # This should be quite fast as it uses a limit and fields are indexed
        # moreover the method is cached
        rule_parameter = self.env['hr.rule.parameter.value'].search([
            ('code', '=', code),
            ('date_from', '<=', date)], limit=1)
        if rule_parameter:
            return safe_eval(rule_parameter.parameter_value)
        if raise_if_not_found:
            raise UserError(_('No rule parameter with code "%(code)s" was found for %(date)s', code=code, date=date))
        else:
            return None

    @api.depends('parameter_version_ids')
    def _compute_current_value(self):
        for rule_parameter in self:
            if not rule_parameter.parameter_version_ids:
                rule_parameter.current_value_one_line = False
                rule_parameter.valid_since = False
                continue

            # All values are already order from most recent to oldest.
            # Here we get the first value that is not in the future, i.e. the current value.
            for value_id in rule_parameter.parameter_version_ids:
                if value_id.date_from <= fields.Date.today():
                    parameter_value = value_id.parameter_value or ''
                    is_number = parameter_value.replace('-', '').replace('.', '').isnumeric()
                    rule_parameter.current_value_one_line = parameter_value if is_number else '(...)'
                    rule_parameter.valid_since = value_id.date_from
                    break

    def _compute_salary_rule(self):
        for rule_parameter in self:
            rule_parameter.salary_rule_ids = self.env['hr.salary.rule'].search([
                '|',
                '|',
                ('condition_python', 'like', "'" + rule_parameter.code + "'"),
                ('amount_python_compute', 'like', "'" + rule_parameter.code + "'"),
                '|',
                ('condition_python', 'like', '"' + rule_parameter.code + '"'),
                ('amount_python_compute', 'like', '"' + rule_parameter.code + '"'),
            ]) if rule_parameter.code else False
            rule_parameter.salary_rule_count = len(rule_parameter.salary_rule_ids)

    def action_open_salary_rules(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_salary_rule_form')
        action.update({
            'domain': [
                '|',
                '|',
                ('condition_python', 'like', "'" + self.code + "'"),
                ('amount_python_compute', 'like', "'" + self.code + "'"),
                '|',
                ('condition_python', 'like', '"' + self.code + '"'),
                ('amount_python_compute', 'like', '"' + self.code + '"'),
            ],
        })
        return action
