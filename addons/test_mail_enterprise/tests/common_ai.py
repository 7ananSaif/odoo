# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.test_mail.tests.test_mail_composer import TestMailComposer


class MailCommonAI(TestMailComposer):
    def _wrap_prompt(self, content):
        return f"""<div class="o_editor_prompt"><div class="o_editor_prompt_content">{content}</div></div>"""

    @contextmanager
    def _patch_agent_generate_response(self, response=None, body_html=None):
        """Patch the _generate_response method of the AI agent to control its output."""

        def _generate_response_patch(*args, **kwargs):
            if isinstance(response, Exception):
                raise response
            return response

        with patch.object(
            self.env.registry["ai.agent"],
            "_generate_response",
            side_effect=_generate_response_patch,
        ):
            if body_html:
                self.template.body_html = body_html
            yield

    @contextmanager
    def _patch_template_eval_prompts(self):
        """Patch the _eval_ai_prompts method to capture the HTML to be evaluated."""
        original_eval_prompts = self.env.registry["ai.agent"]._eval_ai_prompts

        html_to_eval = [None]

        def get_html_to_eval():
            return html_to_eval[0]

        def _eval_ai_prompts_patch(self, html, *args, **kwargs):
            html_to_eval[0] = html
            return original_eval_prompts(self, html, *args, **kwargs)

        with patch.object(self.env.registry["ai.agent"], "_eval_ai_prompts", _eval_ai_prompts_patch):
            yield get_html_to_eval
