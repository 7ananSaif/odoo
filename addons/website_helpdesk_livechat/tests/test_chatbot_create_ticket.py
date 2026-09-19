# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.addons.website_helpdesk_livechat.tests.helpdesk_livechat_chatbot_common import HelpdeskChatbotCase
from odoo.tests import new_test_user, tagged


@tagged("post_install", "-at_install")
class TestChatbotCreateTicket(HelpdeskChatbotCase):

    def test_chatbot_helpdesk_ticket_public_user(self):
        """ Create a ticket from a public user and check that information are correctly propagated. """
        created_ticket = self._chatbot_create_helpdesk_ticket()
        self.assertEqual(created_ticket.partner_email, 'helpme@example.com')
        self.assertEqual(created_ticket.partner_phone, '+32499112233')

        self.assertIn('There is a problem with my printer.', created_ticket.description)
        self.assertIn('helpme@example.com', created_ticket.description)
        self.assertIn('+32499112233', created_ticket.description)

        self.assertFalse(bool(created_ticket.team_id))

    def test_chatbot_helpdesk_ticket_portal_user(self):
        """ Create a ticket from a portal user and check that information are correctly propagated. """
        self.authenticate(self.user_portal.login, self.user_portal.login)
        self.step_helpdesk_create_ticket.write({'helpdesk_team_id': self.helpdesk_team.id})
        created_ticket = self._chatbot_create_helpdesk_ticket()
        # should use email defined on base partner since it's not empty
        self.assertNotEqual(created_ticket.partner_email, "helpme@example.com")
        # phone however WAS empty -> check that it has been updated
        self.assertEqual(created_ticket.partner_phone, '+32499112233')

        self.assertEqual(created_ticket.team_id, self.helpdesk_team)

    def _chatbot_create_helpdesk_ticket(self):
        data = self.make_jsonrpc_request("/im_livechat/get_session", {
            'channel_id': self.livechat_channel.id,
            'chatbot_script_id': self.chatbot_script.id,
        })
        discuss_channel = self.env['discuss.channel'].sudo().browse(data["channel_id"])

        self._post_answer_and_trigger_next_step(
            discuss_channel, chatbot_script_answer=self.step_selection_ticket
        )

        self.assertEqual(discuss_channel.chatbot_current_step_id, self.step_helpdesk_issue)
        self._post_answer_and_trigger_next_step(discuss_channel, 'There is a problem with my printer.')

        self.assertEqual(discuss_channel.chatbot_current_step_id, self.step_helpdesk_email)
        self._post_answer_and_trigger_next_step(discuss_channel, email="helpme@example.com")

        self.assertEqual(discuss_channel.chatbot_current_step_id, self.step_helpdesk_phone)
        self._post_answer_and_trigger_next_step(discuss_channel, '+32499112233')

        self.assertEqual(discuss_channel.chatbot_current_step_id, self.step_helpdesk_create_ticket)
        return self.env["helpdesk.ticket"].search(
            [("origin_channel_id", "=", discuss_channel.id)], order="id desc", limit=1
        )

    def test_create_ticket_from_chatbot(self):
        helpdesk_team = self.env["helpdesk.team"].create({"name": "Helpdesk Team"})
        chatbot_script = self.env["chatbot.script"].create({"title": "Create ticket bot"})
        self.env["chatbot.script.step"].create(
            [
                {
                    "chatbot_script_id": chatbot_script.id,
                    "message": "Hello, how can I help you?",
                    "step_type": "free_input_single",
                },
                {
                    "step_type": "question_email",
                    "chatbot_script_id": chatbot_script.id,
                    "message": "Would you mind leaving your email address so that we can reach you back?",
                },
                {
                    "step_type": "create_ticket",
                    "helpdesk_team_id": helpdesk_team.id,
                    "chatbot_script_id": chatbot_script.id,
                    "message": "Thank you, you should hear back from us very soon!",
                },
            ]
        )
        livechat_channel = self.env["im_livechat.channel"].create(
            {
                "name": "Create ticket channel",
                "rule_ids": [
                    Command.create(
                        {
                            "regex_url": "/",
                            "chatbot_script_id": chatbot_script.id,
                        }
                    )
                ],
            }
        )
        self.start_tour(
            f"/im_livechat/support/{livechat_channel.id}", "website_helpdesk_livechat.create_ticket_from_chatbot"
        )
        ticket = self.env["helpdesk.ticket"].search([("origin_channel_id", "=", livechat_channel.channel_ids.id)])
        self.assertEqual(ticket.name, "I'd like to know more about the Helpdesk application.")
