# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import tagged, users


@tagged('post_install', '-at_install')
class TestAppraisalPublicAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({'name': 'mami rock'})
        cls.user_without_hr_right = mail_new_test_user(
            cls.env,
            name='user_without_hr_right',
            login='user_without_hr_right',
            email='user_without_hr_right@example.com',
            groups='base.group_user',
            notification_type='email',
            company_id=cls.company.id,
        )

        cls.manager = cls.env['hr.employee'].create({
            'name': 'Johnny',
            'user_id': cls.user_without_hr_right.id,
            'company_id': cls.company.id,
        })

        cls.employee_a, cls.employee_b = cls.env['hr.employee'].create([{
            'name': 'David',
            'parent_id': cls.manager.id,
            'company_id': cls.company.id,
            'wage': 1,
            'contract_date_start': '2017-12-05',
            'next_appraisal_date': '2057-12-05',
        }, {
            'name': 'Laura',
            'company_id': cls.company.id,
            'wage': 1,
            'contract_date_start': '2018-12-05',
            'next_appraisal_date': '2058-12-05',
        }])
        cls.employee_c = cls.env['hr.employee'].create({
            'name': 'Jade',
            'parent_id': cls.employee_a.id,
            'company_id': cls.company.id,
            'wage': 1,
            'contract_date_start': '2019-12-05',
            'next_appraisal_date': '2059-12-05',
        })

    def test_manager(self):
        with self.with_user(self.user_without_hr_right.login):
            david, laura, jade = self.env['hr.employee.public'].browse((self.employee_a | self.employee_b | self.employee_c).ids)

            self.assertTrue(david.is_manager)
            self.assertFalse(laura.is_manager)
            self.assertTrue(jade.is_manager)

    def test_manager_access_read(self):
        with self.with_user(self.user_without_hr_right.login):
            david, laura, jade = self.env['hr.employee.public'].browse((self.employee_a | self.employee_b | self.employee_c).ids)

            # Should be able to read direct reports and indirect reports birthday_public_display_string
            self.assertEqual(str(david.next_appraisal_date), '2057-12-05')
            self.assertEqual(str(jade.next_appraisal_date), '2059-12-05')
            # Cannot read values of "manager only field" on an employee the user is not manager of
            self.assertFalse(laura.next_appraisal_date)

    def test_manager_access_search(self):
        with self.with_user(self.user_without_hr_right.login):
            employees = self.env['hr.employee.public'].search([('next_appraisal_date', '>=', '2057-12-05')])

            # Should not find Laura as the user is not her manager
            self.assertEqual(len(employees), 2)
            self.assertTrue('Laura' not in employees.mapped('name'))

    @users('user_without_hr_right')
    def test_appraisal_flow_without_hr_right(self):
        appraisal = self.env['hr.appraisal'].create({'employee_id': self.employee_a.id, 'manager_ids': self.env.user.employee_ids.ids})
        # A manager without hr right should be able to confirm an appraisal of one of his subordinate
        appraisal.action_confirm()
        # A manager without hr right should be able to mark as done an appraisal of one of his subordinate
        appraisal.action_done()
