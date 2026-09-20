from werkzeug.exceptions import NotFound

from odoo import http
from odoo.addons.mail.tools.discuss import add_guest_to_context
from odoo.addons.mail.controllers.thread import ThreadController


class AIController(ThreadController):

    # auth=public to allow visitors to interact with ai agents through livechat
    @http.route(["/ai/generate_response"], type="jsonrpc", auth="public")
    @add_guest_to_context
    def generate_response(self, mail_message_id, channel_id, current_view_info=None, ai_session_identifier=None):
        channel = self._get_ai_channel_from_id(channel_id)
        if not channel:
            raise NotFound()
        message = self._get_message_with_access(mail_message_id)
        if message:
            channel.sudo().ai_agent_id.with_context(current_view_info=current_view_info, ai_session_identifier=ai_session_identifier)._generate_response_for_channel(message, channel)

    @http.route('/ai/close_ai_chat', methods=["POST"], type="jsonrpc", auth='public')
    @add_guest_to_context
    def close_ai_chat(self, channel_id):
        channel = self._get_ai_channel_from_id(channel_id)
        if channel and self._should_unlink_on_close(channel):
            channel.sudo().unlink()

    def _should_unlink_on_close(self, channel):
        return channel.is_member

    def _get_ai_channel_from_id(self, channel_id):
        channel = self.env['discuss.channel'].search([('id', '=', channel_id)])
        if channel.sudo().ai_agent_id:
            return channel
        return self.env['discuss.channel']
