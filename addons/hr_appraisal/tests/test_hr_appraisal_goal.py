# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form, tagged
from odoo.tests.common import HttpCase


@tagged("-at_install", "post_install")
class TestHrAppraisalGoal(HttpCase):
    """Tests covering Appraisal Goals"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["hr.employee"].create(
            {
                "name": "Trixie Lulamoon",
            },
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Pinkie Pie",
                "parent_id": cls.manager.id,
            }
        )
        cls.appraisal = cls.env["hr.appraisal"].create(
            {
                "employee_id": cls.employee.id,
                "manager_ids": cls.manager.ids,
            }
        )
        cls.user_without_hr_right = cls.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
            'notification_type': 'email',
        })
        cls.user_without_hr_right.action_create_employee()
        cls.employee_without_hr_right = cls.user_without_hr_right.employee_ids[0]
        cls.employee_subordinate = cls.env['hr.employee'].create({
            'name': 'Gerard',
            'parent_id': cls.employee_without_hr_right.id,
        })

    def test_create_goal_without_hr_right(self):
        goal_form = Form(self.env['hr.appraisal.goal'].with_user(self.user_without_hr_right).with_context(
            {'uid': self.user_without_hr_right.id}
        ))
        goal_form.name = "My goal"
        goal_form.employee_ids = self.employee_subordinate
        goal_form.save()

    def test_appraisal_goal_autocompletion(self):
        """
        See if the employee and manager fields are auto-completed correctly on
        creation with smart buttons
        """
        self.start_tour(
            f"/odoo/appraisals/{self.appraisal.id}",
            "appraisals_create_appraisal_goal_from_smart_button",
            login="admin",
        )
        self.start_tour(
            f"/odoo/employees/{self.employee.id}",
            "employees_create_appraisal_goal_from_smart_button",
            login="admin",
        )
        autocompleted_goals = self.env["hr.appraisal.goal"].search(
            [
                ("employee_ids", "=", self.employee.id),
                ("manager_ids", "=", self.manager.id),
            ]
        )
        self.assertEqual(len(autocompleted_goals), 2,
            "Two appraisal goals with automatically filled employee and \
            manager inputs should have been created",
        )

    def test_security_rule_goal(self):
        user1, user2, user3 = self.env['res.users'].create([
            {
                'name': 'User 1',
                'login': 'user1',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
                'notification_type': 'email',
            }, {
                'name': 'User 2',
                'login': 'user2',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
                'notification_type': 'email',
            }, {
                'name': 'User 3',
                'login': 'user3',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
                'notification_type': 'email',
            },
        ])
        # emp1 -(manager of)-> emp2 -(manager of)-> emp3
        emp1, emp2, emp3 = self.env['hr.employee'].create([
            {
                "name": "Emp 1",
                "user_id": user1.id,
            },
            {
                "name": "Emp 2",
                "user_id": user2.id,
            },
            {
                "name": "Emp 3",
                "user_id": user3.id,
            },
        ])
        emp3.parent_id = emp2
        emp2.parent_id = emp1
        self.env['hr.appraisal.goal'].create([
            {
                "name": "Goal 1",
                "employee_ids": emp1.ids
            }, {
                "name": "Goal 2",
                "employee_ids": emp2.ids
            }, {
                "name": "Goal 3",
                "employee_ids": emp3.ids
            },
        ])
        with self.with_user('user1'):
            goals = self.env['hr.appraisal.goal'].search([])
            self.assertEqual(len(goals.ids), 3)

        with self.with_user('user2'):
            goals = self.env['hr.appraisal.goal'].search([])
            emp3_goals = goals.filtered_domain([('employee_ids', 'in', emp3.ids)])
            emp1_goals = goals.filtered_domain([('employee_ids', 'in', emp1.ids)])
            self.assertEqual(len(goals.ids), 2)
            self.assertTrue(emp3_goals, "Employee 2 should be able to see the goals of his subordinate")
            self.assertFalse(emp1_goals, "Employee 2 should not be able to see the goals of his manager")

        with self.with_user('user3'):
            goals = self.env['hr.appraisal.goal'].search([])
            self.assertEqual(len(goals.ids), 1)
