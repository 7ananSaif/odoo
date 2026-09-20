# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.addons.test_mail_enterprise.tests.common_ai import MailCommonAI


@tagged("post_install", "-at_install")
class TestMailTemplateAI(MailCommonAI):
    def setUp(self):
        super().setUp()
        self.template.write({
            "model_id": self.env.ref("test_mail.model_mail_test_simple").id,
            "body_html": False,
        })

    def test_prompt_empty_content(self):
        test_record = self.env["mail.test.simple"].create({"name": "name_A", "email_from": "name_B"})
        with self._patch_agent_generate_response(
            body_html=f"""<div><p>Test</p>{self._wrap_prompt("")}</div>""",
        ):
            rendered = self.template._render_field("body_html", [test_record.id])
            self.assertEqual(
                rendered[test_record.id],
                "<div><p>Test</p></div>",
                msg="Empty prompt should be removed.",
            )

    def test_prompt_sanitized_content(self):
        test_record = self.env["mail.test.simple"].create({"name": "name_A", "email_from": "name_B"})

        with self._patch_agent_generate_response(
            response=["foo<img src=x onerror='alert(1)'/><script>alert('Test')</script>"],
            body_html=f"""<div>{self._wrap_prompt("Test")}</div>""",
        ):
            rendered = self.template._render_field("body_html", [test_record.id])
            self.assertEqual(
                rendered[test_record.id],
                '<div><p>foo<img src="x"></p></div>',
                msg="Should sanitize the prompt content.",
            )
