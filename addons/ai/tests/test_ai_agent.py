# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAIAgent(TransactionCase):

    def test_close_chat_only_works_with_ai_channel(self):
        partner = self.env["res.partner"].create({
            "name": "Odoo AI"
        })

        agent = self.env["ai.agent"].create({
            "name": "Odoo AI",
            "partner_id": partner.id

        })
        ai_chat_channel = agent._get_or_create_ai_chat()
        regular_channel = self.env["discuss.channel"].create({
            "channel_member_ids": [
                Command.create(
                    {
                        "partner_id": self.env.user.partner_id.id,
                    }
                ),
            ],
            "channel_type": "chat",
            "name": "Non AI chat"
        })

        agent.close_chat(ai_chat_channel.id)
        agent.close_chat(regular_channel.id)
        self.assertFalse(ai_chat_channel.exists(), "Channel of type 'ai_chat' should be deleted when closed.")
        self.assertTrue(regular_channel.exists(), "Only channels in ['ai_chat', 'ai_composer'] should be deleted on close.")

    def test_generate_response_no_duplicate_user_prompt(self):
        """Test that user prompts are not duplicated when calling _generate_response"""
        agent = self.env["ai.agent"].create({
            "name": "Test AI Agent",
            "llm_model": "gpt-4",
        })
        channel = agent._get_or_create_ai_chat()

        # First 2 messages to simulate first question and response
        channel.message_post(
            body="first question",
            author_id=self.env.user.partner_id.id,
            message_type='comment',
        )
        channel.message_post(
            body="Sure, I'm here to help. What's your first question?",
            author_id=agent.partner_id.id,
            message_type='comment',
        )

        # Post a new message and followed by an explicit generate response call.
        # In the generate response, we check that the user prompt is not duplicated.
        channel.message_post(
            body="second question",
            author_id=self.env.user.partner_id.id,
            message_type='comment',
        )
        with patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request') as mock_request, \
             patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token') as mock_token:
            mock_token.return_value = 'test-api-key'
            mock_request.return_value = {
                'output': [{
                    'type': 'message',
                    'content': [{
                        'type': 'text',
                        'text': 'Response to second question',
                    }],
                }],
            }

            agent._generate_response(prompt="second question")

            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args.kwargs
            messages = call_kwargs['body']['input']

            user_messages = [msg for msg in messages if msg.get('role') == 'user']
            second_question_count = sum(1 for msg in user_messages if msg.get('content') == 'second question')

            self.assertEqual(second_question_count, 1, "User prompt 'second question' should appear only once in messages")

    def test_get_or_create_ai_chat_returns_single_channel(self):
        """Ensure _get_or_create_ai_chat always returns a single channel even if multiple exist."""
        agent = self.env["ai.agent"].create({
            "name": "Test Agent",
        })
        # create the first AI chat channel
        agent._get_or_create_ai_chat()

        # manually create a second AI chat channel for the same agent
        self.env["discuss.channel"].create({
            "channel_member_ids": [
                Command.create({"partner_id": self.env.user.partner_id.id}),
            ],
            "channel_type": "ai_chat",
            "ai_agent_id": agent.id,
            "name": "Extra AI chat",
        })

        # call again: should return a single record
        channel = agent._get_or_create_ai_chat()
        self.assertEqual(len(channel), 1, "Should always return exactly one AI chat channel")

    def test_action_ask_ai_always_opens_a_new_channel(self):
        """Ensure action_ask_ai always opens a new ai chat channel."""
        agent = self.env["ai.agent"].create({"name": "Odoo AI"})

        action_1 = agent.action_ask_ai("Hello, AI!")
        action_2 = agent.action_ask_ai("Hello, AI, again!")

        self.assertLess(
            action_1["params"]["channelId"],
            action_2["params"]["channelId"],
            "Each call to 'action_ask_ai' should open a new ai chat channel."
        )

    def test_get_llm_response_with_sources(self):
        """Responses include source links when the LLM returns attachment ids."""
        agent = self.env["ai.agent"].create({
            "name": "Odoo Agent",
        })

        attachment = self.env["ir.attachment"].create({
            "name": "Doc 1",
            "raw": b"content",
            "mimetype": "text/plain",
        })
        self.env["ai.agent.source"].create({
            "name": "Doc 1",
            "agent_id": agent.id,
            "attachment_id": attachment.id,
            "type": "binary",
            "status": "indexed",
            "is_active": True,
        })

        message = f"Here is your answer [SOURCE:{attachment.id}]"
        llm_response = agent._get_llm_response_with_sources([message])

        self.assertEqual(len(llm_response), 1)
        self.assertNotIn("[SOURCE", llm_response[0])
        self.assertIn("href=\"%s/web/content/%s\"" % (agent.get_base_url(), attachment.id), llm_response[0])
        self.assertIn("[1]", llm_response[0])
