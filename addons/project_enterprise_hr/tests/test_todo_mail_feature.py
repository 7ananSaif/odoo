from odoo.addons.mail.tests.common import MailCommon
from odoo.addons.project.tests.test_project_base import TestProjectCommon
from odoo.addons.test_mail.data.test_mail_data import MAIL_TEMPLATE
from odoo.tests import new_test_user


class TestTodoMailFeatures(TestProjectCommon, MailCommon):

    def test_todo_mail_alais_assignees_from_recipient_list(self):
        todo_alias = self.env.ref('project_enterprise_hr.mail_alias_todo')
        self.assertTrue(todo_alias, "To-Do alais has been archived or deleted")
        # Creating employee for a internal user as the to do alias can only be used by employees
        self.user_projectmanager.action_create_employee()
        self.assertTrue(self.user_projectmanager.employee_id, "The user should have a employee linked")
        self.assertFalse(self.user_projectuser.employee_id, "The user should not have a employee linked")
        new_user = new_test_user(self.env, login='todomailman')
        new_partner = self.env["res.partner"].create({
            'name': 'Test Partner',
            'email': 'test@partner.com',
        })
        incoming_to = (
            f"to-do@{self.env.company.alias_domain_id.name},"
            f"{self.user_public.email},"
            f"{self.user_portal.email},"
            f"{self.user_projectuser.email},"
        )
        cc = (
            f"{new_user.email},"
            f"{new_partner.email},"
        )
        with self.mock_mail_gateway():
            # mail from user having employee linked
            task = self.format_and_process(
                MAIL_TEMPLATE,
                self.user_projectmanager.email,
                incoming_to,
                cc=cc,
                subject="Test todo assignees from address of mail",
                target_model='project.task',
            )
            # mail from user not having employee linked
            task_user = self.format_and_process(
                MAIL_TEMPLATE,
                self.user_projectuser.email,
                incoming_to,
                subject="Test todo assignees from address of mail of user with no employee linked",
                target_model='project.task',
            )
            self.flush_tracking()
        self.assertTrue(task, "To-Do has not been created from a incoming email")
        # only internal users of "from address" are set as asssignees
        self.assertIn(self.user_projectmanager, task.user_ids, "Sender of the email is not added as user in To-Do")
        self.assertEqual(task.user_ids, self.user_projectmanager + self.user_projectuser, "Assignees have not been set of the from address and to of the mail")
        self.assertFalse(task_user, "No To-Do is created as the user doesn't have a employee linked")
        self.assertFalse(task.email_cc, "CC of the mail should not be added to the field email_cc")
        self.assertNotIn(new_user.partner_id, task.message_partner_ids, "Email CC with internal users should not be added into task followers")
