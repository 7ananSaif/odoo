# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPayrollStructure(models.Model):
    _name = 'hr.payroll.structure'
    _description = 'Salary Structure'

    @api.model
    def _get_default_report_id(self):
        return self.env.ref('hr_payroll.action_report_payslip', False)

    @api.model
    def _get_default_rule_ids(self):
        default_structure = self.env.ref('hr_payroll.default_structure', False)
        if not default_structure or not default_structure.rule_ids:
            return []
        vals_list = [rule.copy_data(default={'name': rule.name})[0] for rule in default_structure.rule_ids]
        return [(0, 0, vals) for vals in vals_list]

    def _get_domain_report(self):
        if self.env.company.country_code:
            return [
                ('model', '=', 'hr.payslip'),
                ('report_type', '=', 'qweb-pdf'),
                '|',
                ('report_name', 'ilike', 'l10n_' + self.env.company.country_code.lower()),
                '&',
                ('report_name', 'ilike', 'hr_payroll'),
                ('report_name', 'not ilike', 'l10n')
            ]
        else:
            return [
                ('model', '=', 'hr.payslip'),
                ('report_type', '=', 'qweb-pdf'),
                ('report_name', 'ilike', 'hr_payroll'),
                ('report_name', 'not ilike', 'l10n')
            ]

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    type_id = fields.Many2one(
        'hr.payroll.structure.type', required=True, index=True)
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.company.country_id,
        domain=lambda self: [('id', 'in', self.env.companies.country_id.ids)]
    )
    note = fields.Html(string='Description')
    rule_ids = fields.One2many(
        'hr.salary.rule', 'struct_id', copy=True,
        string='Salary Rules', default=_get_default_rule_ids)
    report_id = fields.Many2one('ir.actions.report',
        string="Template", domain=_get_domain_report, default=_get_default_report_id)
    payslip_name = fields.Char(string="Payslip Name", translate=True,
        help="Name to be set on a payslip. Example: 'End of the year bonus'. If not set, the default value is 'Salary Slip'")
    hide_basic_on_pdf = fields.Boolean(help="Enable this option if you don't want to display the Basic Salary on the printed pdf.")
    unpaid_work_entry_type_ids = fields.Many2many(
        'hr.work.entry.type', 'hr_payroll_structure_hr_work_entry_type_rel')
    use_worked_day_lines = fields.Boolean(default=True, help="Worked days won't be computed/displayed in payslips.")
    schedule_pay = fields.Selection(related='type_id.default_schedule_pay')
    input_line_type_ids = fields.Many2many('hr.payslip.input.type', string='Other Input Line')
    ytd_computation = fields.Boolean(default=False, string='Year to Date Computation',
        help="Adds a column in the payslip that shows the accumulated amount paid for different rules during the year")

    version_properties_definition = fields.PropertiesDefinition("Version Properties Definition")
    payslip_properties_definition = fields.PropertiesDefinition("Payslip Properties Definition")

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=self.env._("%s (copy)", structure.name)) for structure, vals in zip(self, vals_list)]

    def _get_common_payroll_properties(self):
        """
        Helper method to return the common salary inputs between employees and payslips
        """
        payslip_properties = self.payslip_properties_definition or []
        version_properties = self.version_properties_definition or []

        payslip_payroll_keys = {
            prop['name'] for prop in payslip_properties if not prop['name'].startswith('separator_')
        }
        version_payroll_keys = {
            prop['name'] for prop in version_properties if not prop['name'].startswith('separator_')
        }

        # Return the intersection of the two sets
        return list(payslip_payroll_keys & version_payroll_keys)

    def _update_payroll_properties(self, rule_ids, res_model):
        self.ensure_one()
        payslip_properties_definition = self.payslip_properties_definition or []
        version_properties_definition = self.version_properties_definition or []

        def _sort_definition(definition):
            groups = []
            current_group = None
            for prop in definition:
                if prop.get("type") == "separator":
                    if current_group:
                        groups.append(current_group)
                    current_group = [prop, []]
                elif current_group:
                    current_group[1].append(prop)
            if current_group:
                groups.append(current_group)
            cat_ids = []
            for g in groups:
                sep = g[0]
                if sep['name'].startswith('separator_'):
                    cat_id = int(sep['name'][10:])
                    cat_ids.append(cat_id)
            categories = self.env['hr.salary.rule.section'].browse(cat_ids)
            seq_map = {c.id: c.sequence for c in categories}
            groups.sort(key=lambda g: seq_map.get(int(g[0]['name'][10:]), float('inf')))
            new_def = []
            for sep, props in groups:
                new_def.append(sep)
                new_def.extend(props)
            return new_def

        def _add_property_to_definition(definition, rule):
            category = rule.input_section
            if not category:
                raise ValidationError(self.env._('You cannot add a Salary input without a section.'))

            separator_name = f"separator_{category.id}"
            property_name = str(rule.id)
            existing_prop = [prop for prop in definition if prop.get("name") == property_name]

            type = (
                "monetary" if rule.input_unit == "monetary"
                else "boolean" if rule.input_unit == "boolean"
                else "float"
            )
            suffix_base = "% " if rule.input_unit == 'percentage' else ""
            suffix = suffix_base + rule.input_suffix if rule.input_suffix else ""

            if existing_prop:
                existing_prop[0].update({
                    "string": rule.name,
                    "default": rule.input_default_value if type != 'boolean' else rule.input_default_boolean,
                })
                if suffix:
                    existing_prop[0].update({
                        'suffix': suffix
                    })
                return

            new_property = {
                "name": property_name,
                "type": type,
                "string": rule.name,
                "default": rule.input_default_value if type != 'boolean' else rule.input_default_boolean,
            }

            if suffix:
                new_property['suffix'] = suffix

            if type == 'monetary':
                new_property['currency_field'] = 'currency_id'

            sep_index = None
            for i, prop in enumerate(definition):
                if prop.get("type") == "separator" and prop.get("name") == separator_name:
                    sep_index = i
                    break

            if sep_index is not None:
                next_sep_index = len(definition)
                for j in range(sep_index + 1, len(definition)):
                    if definition[j].get("type") == "separator":
                        next_sep_index = j
                        break
                definition.insert(next_sep_index, new_property)
            else:
                new_separator = {
                    "name": separator_name,
                    "type": "separator",
                    "string": category.name,
                    "fold_by_default": False,
                }
                definition.append(new_separator)
                definition.append(new_property)

        dependent_rules = self.env['hr.salary.rule'].search([('dependent_input_id', 'in', rule_ids.ids)])
        all_rules = rule_ids | dependent_rules

        for rule in all_rules:
            if res_model in ['hr.employee', 'hr.version']:
                _add_property_to_definition(version_properties_definition, rule)
            elif res_model == 'hr.payslip':
                _add_property_to_definition(payslip_properties_definition, rule)

        self.write({
            'payslip_properties_definition': _sort_definition(payslip_properties_definition),
        })
        self.write({
            'version_properties_definition': _sort_definition(version_properties_definition),
        })

    def action_get_structure_inputs(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'view_id': self.env.ref("hr_payroll.hr_salary_rule_benefit_selector_list", False).id,
            'res_model': 'hr.salary.rule',
            'target': 'new',
            'domain': [
                ('struct_id', '=', self.id),
                ('condition_select', '=', 'property_input'),
                ('input_usage_employee', '=', True),
                ('dependent_input_id', '=', False),
            ]
        }
