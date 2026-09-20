# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import common, tagged
from odoo.addons.ai.utils.llm_api_service import LLMApiService, _logger as service_logger


@tagged("post_install", "-at_install")
class TestLLMToolCalling(common.TransactionCase):
    def _create_mock_request(self, responses):
        """Create a mock request function that cycles through the given responses."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        return mock_request

    def _create_dummy_tools(self, count=1):
        """Creates a number of dummy tools for testing. Each tool is named 'dummy_tool_X' where X is its number.

        :param int count: The number of dummy tools to create.
        :return: A tuple containing:
            - A dictionary of tools.
            - A lambda function to check if a tool was called, taking the tool name as argument.
        """
        tools = {}
        was_called_flags = {}

        for i in range(1, count + 1):
            tool_name = f"dummy_tool_{i}"
            was_called_flags[tool_name] = [False]

            def create_tool_func(name, flag):

                def dummy_tool(arguments):
                    flag[0] = True
                    return f"{name} result", None

                return dummy_tool

            tools[tool_name] = (
                f"Tool {i}",
                False,
                create_tool_func(tool_name, was_called_flags[tool_name]),
                {"type": "object", "properties": {}, "required": []}
            )

        return tools, lambda key: was_called_flags[key][0]

    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy')
    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request')
    def test_openai_ignore_text_with_tool_call(self, mock_request, mock_token):
        tools, was_called_flags = self._create_dummy_tools(1)

        # First response: thinking text + tool call
        mock_response1 = {
            "output": [
                {"type": "text", "text": "This is the thinking text."},
                {
                    "type": "function_call",
                    "name": "dummy_tool_1",
                    "arguments": "{}",
                    "call_id": "call_123"
                }
            ]
        }

        # Second response: final text after tool call result is sent
        mock_response2 = {
            "output": [
                {"type": "text", "text": "This is the final answer."}
            ]
        }

        mock_request.side_effect = self._create_mock_request([mock_response1, mock_response2])

        service = LLMApiService(self.env, provider='openai')
        response = service.request_llm(
            llm_model='gpt-4o',
            system_prompts=[],
            user_prompts=["test prompt"],
            tools=tools
        )

        self.assertTrue(was_called_flags("dummy_tool_1"))
        self.assertEqual(response, ["This is the final answer."])

    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy')
    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request')
    def test_gemini_ignore_text_with_tool_call(self, mock_request, mock_token):
        tools, was_called_flags = self._create_dummy_tools(1)

        # First response: thinking text + tool call
        mock_response1 = {
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "This is the thinking text."},
                        {"functionCall": {"name": "dummy_tool_1", "args": {}}}
                    ]
                }
            }]
        }

        # Second response: final text after tool call result is sent
        mock_response2 = {
            "candidates": [{
                "content": {"parts": [{"text": "This is the final answer."}]}
            }]
        }

        mock_request.side_effect = self._create_mock_request([mock_response1, mock_response2])

        service = LLMApiService(self.env, provider='google')
        response = service.request_llm(
            llm_model='gemini-1.5-flash',
            system_prompts=[],
            user_prompts=["test prompt"],
            tools=tools
        )

        self.assertTrue(was_called_flags("dummy_tool_1"))
        self.assertEqual(response, ["This is the final answer."])

    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy')
    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request')
    def test_max_api_calls_reached(self, mock_request, mock_token):
        self.env["ir.config_parameter"].sudo().set_param("ai.max_successive_calls", "2")

        tools, __ = self._create_dummy_tools(1)

        # Always return a tool call, never a final text response
        mock_response_tool_call = {
            "output": [
                {
                    "type": "function_call",
                    "name": "dummy_tool_1",
                    "arguments": "{}",
                    "call_id": "call_123"
                }
            ]
        }

        mock_request.return_value = mock_response_tool_call  # Always return the same response

        service = LLMApiService(self.env, provider='openai')

        with self.assertRaises(ValueError) as e:
            service.request_llm(
                llm_model='gpt-4o',
                system_prompts=[],
                user_prompts=["test prompt"],
                tools=tools
            )
        self.assertEqual(
            str(e.exception),
            "Number of successive API calls exceeded, please try again with a more precise request."
        )

        self.assertEqual(mock_request.call_count, 2)

    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy')
    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request')
    def test_max_tool_calls_reached(self, mock_request, mock_token):
        self.env["ir.config_parameter"].sudo().set_param("ai.max_tool_calls_per_call", "1")

        tools, was_called_flags = self._create_dummy_tools(2)

        # First response: 2 tool calls, which is more than the limit of 1
        mock_response1 = {
            "output": [
                {"type": "function_call", "name": "dummy_tool_1", "arguments": "{}", "call_id": "call_1"},
                {"type": "function_call", "name": "dummy_tool_2", "arguments": "{}", "call_id": "call_2"}
            ]
        }

        # Second response: final text answer
        mock_response2 = {
            "output": [
                {"type": "text", "text": "Final answer after handling tool calls."}
            ]
        }

        mock_request.side_effect = self._create_mock_request([mock_response1, mock_response2])

        with self.assertLogs(service_logger, level='WARNING') as mock_service_logger:
            service = LLMApiService(self.env, provider='openai')
            response = service.request_llm(
                llm_model='gpt-4o',
                system_prompts=[],
                user_prompts=["test prompt"],
                tools=tools
            )

        self.assertEqual(response, ["Final answer after handling tool calls."])
        self.assertTrue(was_called_flags("dummy_tool_1"))
        self.assertFalse(was_called_flags("dummy_tool_2"))

        warning_log, = mock_service_logger.records
        self.assertEqual(warning_log.message, "AI: Tool call limit reached, stopping further tool calls")

        # Check the inputs for the second LLM call
        second_call_kwargs = mock_request.call_args.kwargs
        tool_responses = second_call_kwargs['body']['input'][-2:]

        self.assertEqual(tool_responses[0]['type'], 'function_call_output')
        self.assertEqual(tool_responses[0]['call_id'], 'call_1')
        self.assertEqual(tool_responses[0]['output'], "dummy_tool_1 result")

        self.assertEqual(tool_responses[1]['type'], 'function_call_output')
        self.assertEqual(tool_responses[1]['call_id'], 'call_2')
        self.assertEqual(tool_responses[1]['output'], "Error: This tool call isn't processed because of tool call limit, try again")

    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy')
    @patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request')
    def test_unknown_tool_call(self, mock_request, mock_token):
        # First response: a call to a tool that does not exist
        mock_response1 = {
            "output": [
                {"type": "function_call", "name": "unknown_tool", "arguments": "{}", "call_id": "call_1"}
            ]
        }

        # Second response: final text answer
        mock_response2 = {
            "output": [
                {"type": "text", "text": "Final answer after handling unknown tool."}
            ]
        }

        mock_request.side_effect = self._create_mock_request([mock_response1, mock_response2])

        with self.assertLogs(service_logger, level='ERROR') as mock_service_logger:
            service = LLMApiService(self.env, provider='openai')
            response = service.request_llm(
                llm_model='gpt-4o',
                system_prompts=[],
                user_prompts=["test prompt"],
                tools={}
            )
            self.assertEqual(response, ["Final answer after handling unknown tool."])

        error_log, = mock_service_logger.records
        self.assertEqual(error_log.message, "AI: Try to call a forbidden action unknown_tool")

        # Check the inputs for the second LLM call
        second_call_kwargs = mock_request.call_args.kwargs
        tool_response = second_call_kwargs['body']['input'][-1]

        self.assertEqual(tool_response['type'], 'function_call_output')
        self.assertEqual(tool_response['call_id'], 'call_1')
        self.assertEqual(tool_response['output'], "Error: unknown tool 'unknown_tool'. Try again with the correct tool name.")
