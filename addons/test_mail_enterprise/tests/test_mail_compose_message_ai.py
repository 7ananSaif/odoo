# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.addons.test_mail_enterprise.tests.common_ai import MailCommonAI
from odoo.exceptions import AccessError
from odoo.tests import tagged, users, Form
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestMailComposeMessageAI(MailCommonAI):
    def setUp(self):
        super().setUp()
        # rename test records to A, B, C and their customer_id to Cust A, Cust B, Cust C
        for letter, test_record in zip("ABC", self.test_record | self.test_records):
            test_record.write({"name": letter})
            test_record.customer_id.write({"name": f"Cust {letter}"})

    @mute_logger("odoo.addons.mail.models.mail_mail")
    @users("employee")
    def test_composer_rendering_ai_prompt_multi(self):
        with self._patch_agent_generate_response(
            response=["Test response"],
            body_html=f"""<div><t t-out="object.name"/> +++ <t t-out="object.customer_id.name"/>{self._wrap_prompt("Test prompt")}</div>""",
        ):
            composer_form = Form(self.env['mail.compose.message'].with_context(
                self._get_web_context(
                    self.test_records,
                    add_web=True,
                    default_template_id=self.template.id,
                )
            ))
            composer = composer_form.save()

            with self.mock_mail_gateway(), self.mock_mail_app():
                composer._action_send_mail()

            self.assertEqual(len(self._new_mails), 2, 'Should have created 1 mail.mail per record')

            for record in self.test_records:
                message = record.message_ids[0]
                self.assertMailMail(record.customer_id, 'sent',
                                    mail_message=message,
                                    author=self.partner_employee,
                                    email_values={
                                        'email_from': self.partner_employee_2.email_formatted,
                                        'reply_to': 'info@test.example.com',
                                    })
                self.assertEqual(message.body, f"<div>{record.name} +++ {record.customer_id.name}<p>Test response</p></div>")

    @users("employee")
    def test_composer_rendering_ai_prompt_single(self):
        with self._patch_agent_generate_response(
            response=["Test response"],
            body_html=f"""<div><t t-out="object.name"/> +++ <t t-out="object.customer_id.name"/>{self._wrap_prompt("Test prompt")}</div>""",
        ):
            with Form(self.env['mail.compose.message'].with_context(self._get_web_context(
                self.test_record,
                add_web=True,
            ))) as composer:
                composer.template_id = self.template
            self.assertEqual(composer.body, """<div>A +++ Cust A<p>Test response</p></div>""", msg="Evaluated template body_html should be set as the composer body")

    @users("employee")
    def test_composer_dynamic_content(self):
        with self._patch_template_eval_prompts() as get_html_to_eval:
            body_html = f"""<div>{self._wrap_prompt('Greet <t t-out="object.name"/> and his buddy <t t-out="object.customer_id.name"/>')}</div>"""
            expected_html_to_eval = f"""<div>{self._wrap_prompt('Greet A and his buddy Cust A')}</div>"""
            with self._patch_agent_generate_response(
                response=["Test response"],
                body_html=body_html,
            ):
                composer_form = Form(self.env['mail.compose.message'].with_context(self._get_web_context(
                    self.test_record,
                    add_web=True,
                    default_template_id=self.template.id,
                )))
                composer_form.save()
                self.assertEqual(
                    get_html_to_eval(),
                    expected_html_to_eval,
                    msg="Ensure the dynamic fields are evaluated before passing to the agent.",
                )

    @users("employee")
    def test_composer_dynamic_content_access_error(self):
        with self._patch_template_eval_prompts() as get_html_to_eval:
            with self._patch_agent_generate_response(
                response=["Test response"],
                body_html=f"""<div>{self._wrap_prompt('<t t-out="object.name"/> +++ <t t-out="object.phone_number"/>')}</div>""",
            ):
                # clear the user's groups to simulate no access rights to the models used in the template
                self.env.user.write({"group_ids": [Command.clear()]})
                with self.assertRaises(AccessError):
                    composer = Form(self.env['mail.compose.message'].with_context(self._get_web_context(
                        self.test_record,
                        add_web=True,
                        default_template_id=self.template.id,
                    )))
                    composer.save()

                self.assertEqual(
                    get_html_to_eval(),
                    None,
                    msg="There should be no HTML to evaluate if the user has no access to the models used in the template.",
                )

    @mute_logger("odoo.addons.ai.models.mail_render_mixin")
    @users("employee")
    def test_composer_missing_composer_should_remove_prompts(self):
        with patch.object(self.env.registry["ai.composer"], "_unlink_except_default_rules", lambda self: True):
            self.env.ref("ai.ai_mail_template_prompt_evaluator").sudo().unlink()
        with self._patch_template_eval_prompts():
            with self._patch_agent_generate_response(body_html=f"""<div>Test{self._wrap_prompt('Bla')}</div>"""):
                composer_form = Form(self.env['mail.compose.message'].with_context(self._get_web_context(
                    self.test_record,
                    add_web=True,
                    default_template_id=self.template.id,
                )))
                composer = composer_form.save()
                self.assertEqual(composer.body, """<div>Test</div>""", msg="The body should not contain the prompt if the AI composer is missing.")

    @mute_logger("odoo.addons.ai.models.mail_render_mixin")
    @users("employee")
    def test_composer_missing_default_agent_should_remove_prompts(self):
        # Temporarily disable the ondelete constraint for testing
        with patch.object(self.env.registry["ai.agent"], "_unlink_except_system_agent", lambda self: True):
            self.env.ref("ai.ai_default_agent").sudo().unlink()

        with self._patch_template_eval_prompts():
            with self._patch_agent_generate_response(body_html=f"""<div>Test{self._wrap_prompt('Bla')}</div>"""):
                composer_form = Form(self.env['mail.compose.message'].with_context(self._get_web_context(
                    self.test_record,
                    add_web=True,
                    default_template_id=self.template.id,
                )))
                composer = composer_form.save()
                self.assertEqual(composer.body, """<div>Test</div>""", msg="The body should not contain the prompt if the default agent is missing.")
