# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from odoo.tests import Form, TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestHrAppraisalSkills(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = cls.env["res.users"].create(
            {
                "name": "Michael Hawkins",
                "login": "test",
                "group_ids": [(6, 0, [cls.env.ref("hr_appraisal.group_hr_appraisal_user").id])],
                "notification_type": "email",
            }
        )
        cls.hr_employee, cls.hr_employee_2 = cls.env["hr.employee"].create([
            dict(
                name="Michael Hawkins",
                user_id=cls.user.id,
            ),
            dict(
                name="Michel Jardin",
            ),
        ])
        cls.hr_employee_2.parent_id = cls.hr_employee

        cls.appraisal = cls.env["hr.appraisal"].create(
            {
                "employee_id": cls.hr_employee_2.id,
                "state": "2_pending",
                "date_close": date.today() + relativedelta(months=1),
            }
        )

        cls.skill_type = cls.env["hr.skill.type"].create({"name": "Test Skill Type"})
        cls.skill_level_1, cls.skill_level_2, cls.skill_level_3 = cls.env["hr.skill.level"].create(
            [
                {"name": "Level 1", "skill_type_id": cls.skill_type.id, "level_progress": 0},
                {"name": "Level 2", "skill_type_id": cls.skill_type.id, "level_progress": 50},
                {"name": "Level 3", "skill_type_id": cls.skill_type.id, "level_progress": 100},
            ]
        )
        cls.skill = cls.env["hr.skill"].create({"name": "Test Skill", "skill_type_id": cls.skill_type.id})

        cls.appraisal_skill = cls.env["hr.appraisal.skill"].create(
            {
                "skill_type_id": cls.skill_type.id,
                "skill_id": cls.skill.id,
                "skill_level_id": cls.skill_level_1.id,
                "appraisal_id": cls.appraisal.id,
                "valid_from": datetime.today() - relativedelta(months=1),
                "justification": "This value should not change",
            }
        )

    def test_changing_skill_level_preserves_justification_value(self):
        """
        Test that modifying a core field preserves the value of a passive field.

        When an active/core field is modified (triggering versioned skill creation),
        passive fields like 'justification' should be copied to the new version.
        """
        appraisal_form = Form(self.appraisal.with_context(uid=self.user.id))
        old_skills = self.appraisal.appraisal_skill_ids
        index = self.appraisal.current_appraisal_skill_ids.ids.index(self.appraisal_skill.id)
        with appraisal_form.current_appraisal_skill_ids.edit(index) as cas:
            cas.skill_level_id = self.skill_level_2
        appraisal_form.save()
        new_skill = self.appraisal.appraisal_skill_ids - old_skills

        self.assertTrue(new_skill, "Editing an active/core field should create a new skill/record.")
        self.assertEqual(
            new_skill.justification,
            "This value should not change",
            "The justification value should be 'This value should not change'",
        )
        self.assertEqual(
            new_skill.justification,
            old_skills.justification,
            "The new and old skill should have the same value for the 'Justification' field",
        )

    def test_changing_justification_value_should_not_create_new_skill(self):
        """
        Test that modifying a passive field doesn't trigger versioned skill creation.

        When a passive field is modified, the existing record should be updated
        without creating a new versioned record.
        """
        appraisal_form = Form(self.appraisal.with_context(uid=self.user.id))
        old_skills = self.appraisal.appraisal_skill_ids
        index = self.appraisal.current_appraisal_skill_ids.ids.index(self.appraisal_skill.id)
        with appraisal_form.current_appraisal_skill_ids.edit(index) as cas:
            cas.justification = "This should NOT create a new skill"
        appraisal_form.save()
        new_skill = self.appraisal.appraisal_skill_ids - old_skills

        self.assertFalse(new_skill, "Editing a passive field should NOT create a new skill/record.")
        self.assertEqual(
            old_skills.justification,
            "This should NOT create a new skill",
            "The justification should have changed to 'This should NOT create a new skill'",
        )

    def test_create_appraisal_skill_without_hr_right(self):
        user_without_hr_right = self.env['res.users'].create({
            'name': 'Test without hr right',
            'login': 'test_without_hr_right',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'notification_type': 'email',
        })
        user_without_hr_right.action_create_employee()
        employee_1 = self.env['hr.employee'].create([
            {
                'name': 'Emp1',
                'parent_id': user_without_hr_right.employee_ids[0].id,
            }
        ])
        self.env['hr.employee.skill'].create({
            'skill_type_id': self.skill_type.id,
            'skill_id': self.skill.id,
            'skill_level_id': self.skill_level_1.id,
            'employee_id': employee_1.id,
            'valid_from': date(2024, 3, 2),
        })
        with self.with_user(user_without_hr_right.login):
            appraisal_form = Form(self.env['hr.appraisal'])
            appraisal_form.employee_id = employee_1
            employee_1_appraisal = appraisal_form.save()
            employee_1_appraisal.action_confirm()
            self.assertEqual(employee_1_appraisal.appraisal_skill_ids[0].manager_ids, user_without_hr_right.employee_ids[0])
