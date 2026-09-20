from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestSalaryRuleCategory(TransactionCase):

    def setUp(self):
        super().setUp()

        self.existing_category1 = self.env['hr.salary.rule.category'].create({
            'name': 'Existing Category',
            'code': 'EXIST',
            'country_id': self.env.ref('base.fr').id,
        })


    def test_copy_existing_category(self):
        new_category = self.existing_category1.copy()
        self.assertEqual(new_category.name, 'Existing Category (copy)')

    def test_create_category_with_duplicate_code_in_different_country(self):
        category = self.env['hr.salary.rule.category'].create({
            'name': 'Different Country Category',
            'code': 'EXIST',
            'country_id': self.env.ref('base.be').id,
        })
        self.assertTrue(category)

    def test_create_category_with_unique_code(self):
        category = self.env['hr.salary.rule.category'].create({
            'name': 'Unique Category',
            'code': 'UNIQUE_CODE',
            'country_id': self.env.ref('base.be').id,
        })
        self.assertTrue(category)
