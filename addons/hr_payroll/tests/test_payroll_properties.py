# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tests import tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@tagged('payroll_properties')
class TestPayrollProperties(TestPayslipContractBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.structure_type_A = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer A',
        })

        cls.structure_type_B = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer B',
        })

        cls.structure_A = cls.env['hr.payroll.structure'].create({
            'name': 'Main Default Structure',
            'type_id': cls.structure_type_A.id,
        })

        cls.structure_B = cls.env['hr.payroll.structure'].create({
            'name': 'Secondary Structure',
            'type_id': cls.structure_type.id,
        })

        cls.structure_C = cls.env['hr.payroll.structure'].create({
            'name': 'Main Structure C',
            'type_id': cls.structure_type_B.id,
        })

        cls.structure_type_A.default_struct_id = cls.structure_A
        cls.structure_type_B.default_struct_id = cls.structure_C

        cls.category1 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 1'
        })

        cls.category2 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 2'
        })

        cls.category3 = cls.env['hr.salary.rule.section'].create({
            'name': 'Category 3'
        })

        cls.structure_type.default_struct_id = cls.structure_A

        cls.mr_property = cls.env['hr.employee'].create({
            'name': 'Mr. Property',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
        })

        cls.Rule = cls.env['hr.salary.rule']

    def create_property_salary_rule(self, struct_id, code, section, unit='monetary', default_value=0, suffix=False, dependent_input_id=None):
        rule_vals = {
            'name': 'Test Rule',
            'code': code,
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'condition_select': 'property_input',
            'input_section': section.id,
            'input_unit': unit,
            'input_default_value': default_value,
            'input_suffix': suffix,
            'struct_id': struct_id.id
        }
        if dependent_input_id:
            rule_vals['dependent_input_id'] = dependent_input_id.id
        return self.env['hr.salary.rule'].create(rule_vals)

    def generate_payslip(self, struct, date, employee, version=None):
        test_payslip = self.env['hr.payslip'].create({
            'name': 'Property Payslips',
            'employee_id': employee.id if employee else self.richard_emp.id,
            'version_id': version.id if version else employee.version_id.id,
            'company_id': employee.company_id.id,
            'struct_id': struct.id,
            'date_from': date,
            'date_to': date + relativedelta(months=1, days=-1),
        })

        test_payslip.compute_sheet()

        return test_payslip

    def test_add_property_to_version_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_test_1', section=self.category1, default_value=100)
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 2)  # Separator + property
        self.assertEqual(version_def[0]['type'], 'separator')
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], f'{rule.id}')
        self.assertEqual(version_def[1]['type'], 'monetary')
        self.assertEqual(version_def[1]['default'], 100.0)

        payroll_def = self.structure_A.payslip_properties_definition
        self.assertEqual(payroll_def, [])

    def test_add_property_to_payslip_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_test_1', section=self.category1, default_value=100)
        self.structure_A._update_payroll_properties(rule, 'hr.payslip')

        payslip_def = self.structure_A.payslip_properties_definition
        self.assertEqual(len(payslip_def), 2)  # Separator + property
        self.assertEqual(payslip_def[0]['type'], 'separator')
        self.assertEqual(payslip_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(payslip_def[1]['name'], f'{rule.id}')
        self.assertEqual(payslip_def[1]['type'], 'monetary')
        self.assertEqual(payslip_def[1]['default'], 100.0)

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def, [])

    def test_no_duplicate_property_in_version_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_test_dup', section=self.category1, default_value=200)
        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        version_def_initial = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def_initial), 2)

        # Add again
        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        version_def_after = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def_after), 2)
        self.assertEqual(version_def_initial, version_def_after)

    def test_boolean_property_type_in_version_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_bool', section=self.category1, unit='boolean')
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['type'], 'boolean')
        self.assertEqual(version_def[1]['default'], False)

    def test_property_suffix(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, suffix="Per month", unit='monetary')
        rule_percentage = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_percentage', section=self.category1, suffix="Per month", unit='percentage')
        self.structure_A._update_payroll_properties(rule + rule_percentage, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['suffix'], 'Per month')
        self.assertEqual(version_def[2]['suffix'], '% Per month')

    def test_compute_input_used_in_definition(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, unit='monetary')
        rule_percentage = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_percentage', section=self.category1, unit='percentage')

        self.assertFalse(rule.input_used_in_definition)
        self.assertFalse(rule_percentage.input_used_in_definition)

        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        self.env.flush_all()
        (rule + rule_percentage)._compute_input_used_in_definition()
        self.assertTrue(rule.input_used_in_definition)
        self.assertFalse(rule_percentage.input_used_in_definition)

        self.structure_A._update_payroll_properties(rule_percentage, 'hr.employee')
        self.env.flush_all()
        (rule + rule_percentage)._compute_input_used_in_definition()
        self.assertTrue(rule.input_used_in_definition)
        self.assertTrue(rule_percentage.input_used_in_definition)

    def test_update_property_suffix(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, unit='monetary')
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertFalse('suffix' in version_def[1])

        rule.input_suffix = 'Test Suffix'
        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['suffix'], 'Test Suffix')

    def test_update_property_default_value(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, unit='monetary', default_value=150)
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['default'], 150)

        rule.input_default_value = 400
        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['default'], 400)

    def test_update_property_name(self):
        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_monetary', section=self.category1, unit='monetary', default_value=150)
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['string'], "Test Rule")

        rule.name = "Renamed rule"
        self.structure_A._update_payroll_properties(rule, 'hr.employee')
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(version_def[1]['string'], "Renamed rule")

    def test_multiple_rules_same_category_in_version_definition(self):
        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_multi1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_multi2', section=self.category1, default_value=20)
        self.structure_A._update_payroll_properties(rule1 + rule2, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 3)  # Separator + 2 properties
        self.assertEqual(version_def[0]['type'], 'separator')
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        prop_names = [prop['name'] for prop in version_def[1:]]
        self.assertIn(str(rule1.id), prop_names)
        self.assertIn(str(rule2.id), prop_names)

    def test_multiple_categories_in_version_definition(self):
        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)
        self.structure_A._update_payroll_properties(rule1 + rule2, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], str(rule1.id))
        self.assertEqual(version_def[2]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[3]['name'], str(rule2.id))

    def test_salary_rule_section_sequence_ordering(self):
        self.category1.sequence = 432
        self.category2.sequence = 99
        self.category3.sequence = 667

        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)
        rule3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat3', section=self.category3, default_value=20)
        self.structure_A._update_payroll_properties(rule1 + rule2 + rule3, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 6)  # 3 separators + 3 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[1]['name'], str(rule2.id))
        self.assertEqual(version_def[2]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[3]['name'], str(rule1.id))
        self.assertEqual(version_def[4]['name'], f'separator_{self.category3.id}')
        self.assertEqual(version_def[5]['name'], str(rule3.id))

    def test_property_inserted_in_right_section(self):
        self.category1.sequence = 432
        self.category2.sequence = 99

        rule1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat1', section=self.category1, default_value=10)
        rule2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_cat2', section=self.category2, default_value=20)
        self.structure_A._update_payroll_properties(rule1, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 2)  # 1 separators + 1 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], str(rule1.id))

        self.structure_A._update_payroll_properties(rule2, 'hr.employee')
        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        self.assertEqual(version_def[0]['name'], f'separator_{self.category2.id}')
        self.assertEqual(version_def[1]['name'], str(rule2.id))
        self.assertEqual(version_def[2]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[3]['name'], str(rule1.id))

    def test_insert_position_existing_separator_in_version_definition(self):
        # Pre-populate with existing separator and property
        self.structure_A.version_properties_definition = [
            {'name': f'separator_{self.category1.id}', 'type': 'separator', 'string': self.category1.name},
            {'name': 'existing_prop', 'type': 'float', 'string': 'Existing Prop', 'default': 0.0},
            {'name': f'separator_{self.category2.id}', 'type': 'separator', 'string': self.category2.name},
        ]

        rule = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_insert', section=self.category1, default_value=50)
        self.structure_A._update_payroll_properties(rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # Original 3 + 1 new property
        self.assertEqual(version_def[0]['type'], 'separator')  # category1 separator
        self.assertEqual(version_def[0]['name'], f'separator_{self.category1.id}')
        self.assertEqual(version_def[1]['name'], 'existing_prop')
        self.assertEqual(version_def[2]['name'], str(rule.id))  # Inserted before category2 separator
        self.assertEqual(version_def[3]['type'], 'separator')  # category2 separator
        self.assertEqual(version_def[3]['name'], f'separator_{self.category2.id}')

    def test_dependent_rules_in_version_definition(self):
        parent_rule = self.create_property_salary_rule(struct_id=self.structure_A, code='parent_rule', section=self.category1, default_value=100)
        dependent_rule = self.create_property_salary_rule(struct_id=self.structure_A, code='dep_rule', section=self.category2, default_value=200, dependent_input_id=parent_rule)

        self.structure_A._update_payroll_properties(parent_rule, 'hr.employee')

        version_def = self.structure_A.version_properties_definition
        self.assertEqual(len(version_def), 4)  # 2 separators + 2 properties
        prop_names = [p['name'] for p in version_def if p.get('type') != 'separator']
        self.assertIn(str(parent_rule.id), prop_names)
        self.assertIn(str(dependent_rule.id), prop_names)

    def test_properties_set_with_structure_type(self):

        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')

        rule_4 = self.create_property_salary_rule(struct_id=self.structure_C, code='rule_c_1', section=self.category1, default_value=250)
        rule_5 = self.create_property_salary_rule(struct_id=self.structure_C, code='rule_c_2', section=self.category1, default_value=300)
        self.structure_C._update_payroll_properties(rule_4 + rule_5, 'hr.employee')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.assertDictEqual(dict(self.mr_property.version_id.payroll_properties), {str(rule_1.id): 100.0, str(rule_2.id): 150.0, str(rule_3.id): 200.0})

        self.mr_property.version_id.structure_type_id = self.structure_type_B
        self.assertDictEqual(dict(self.mr_property.version_id.payroll_properties), {str(rule_4.id): 250.0, str(rule_5.id): 300.0})

    def test_property_get_operation_on_version(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_1'), 100)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_2'), 150)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_3'), 200)

    def test_property_set_operation_on_version(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id._set_property_input_value('rule_a_1', 999)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_2'), 150)
        self.assertEqual(self.mr_property.version_id._get_property_input_value('rule_a_3'), 200)

    def test_properties_copy_and_update_on_version(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id._set_property_input_value('rule_a_1', 999)
        self.mr_property.version_id._set_property_input_value('rule_a_2', 998)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 997)

        self.mr_property.create_version({
            'date_version': date(2025, 1, 1)
        })

        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_3'), 997)

        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_3'), 997)

        self.mr_property.version_ids[1]._set_property_input_value('rule_a_1', 444)

        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_1'), 999)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[0]._get_property_input_value('rule_a_3'), 997)

        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_1'), 444)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_2'), 998)
        self.assertEqual(self.mr_property.version_ids[1]._get_property_input_value('rule_a_3'), 997)

    def test_properties_computed_on_payslip(self):
        """
        Given 3 property rules A, B and C, if A and C and common to both the version and the payslip property definition.
        At payslip creation, the payslip should take the values of the version inputs A and C
        """

        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')
        self.structure_A._update_payroll_properties(rule_1 + rule_3, 'hr.payslip')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)

        self.assertDictEqual(dict(property_slip.payslip_properties), {str(rule_1.id): 123.0, str(rule_3.id): 456.0})

    def test_localdict_compute(self):
        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')
        self.structure_A._update_payroll_properties(rule_1 + rule_3, 'hr.payslip')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)
        self.assertDictEqual(property_slip._get_localdict()['property_inputs'], {rule_1.id: 123.0, rule_2.id: 150.0, rule_3.id: 456.0})

    def test_properties_payslip_lines(self):

        rule_1 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_1', section=self.category1, default_value=100)
        rule_2 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_2', section=self.category2, default_value=150)
        rule_3 = self.create_property_salary_rule(struct_id=self.structure_A, code='rule_a_3', section=self.category2, default_value=200)
        self.structure_A._update_payroll_properties(rule_1 + rule_2 + rule_3, 'hr.employee')
        self.structure_A._update_payroll_properties(rule_1 + rule_3, 'hr.payslip')

        self.mr_property.version_id.structure_type_id = self.structure_type_A
        self.mr_property.version_id.contract_date_start = date(2025, 1, 1)
        self.mr_property.version_id._set_property_input_value('rule_a_1', 123)
        self.mr_property.version_id._set_property_input_value('rule_a_3', 456)

        property_slip = self.generate_payslip(struct=self.structure_A, date=date(2025, 1, 1), employee=self.mr_property)
        line_values = property_slip._get_line_values(self.structure_A.rule_ids.mapped('code'), compute_sum=True)
        self.assertEqual(line_values['rule_a_1']['sum']['total'], 123)
        self.assertEqual(line_values['rule_a_2']['sum']['total'], 150)
        self.assertEqual(line_values['rule_a_3']['sum']['total'], 456)
