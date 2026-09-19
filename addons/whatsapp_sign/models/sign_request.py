# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError
from odoo.tools.i18n import format_list


class SignRequest(models.Model):
    _inherit = 'sign.request'

    send_channel = fields.Selection(
        selection_add=[("whatsapp", "WhatsApp")],
        ondelete={"whatsapp": "set default"},  # go back to email if whatsapp was removed
    )
    signers_name = fields.Char(compute='_compute_signers_name', string='Signers name')
    refuser_partner = fields.Many2one('res.partner', compute='_compute_refuser_partner', string="Refuser Partner")
    refusal_reason = fields.Char(string="Refusal reason")
    raw_optional_message = fields.Char(compute='_compute_raw_optional_message', string="Optional Message")

    @api.constrains('send_channel')
    def _check_send_channel(self):
        whatsapp_sign_configured = self.env['sign.request.item']._check_whatsapp_template_exists()
        for sign_request in self:
            if sign_request.send_channel == 'whatsapp' and not whatsapp_sign_configured:
                raise ValidationError(
                    self.env._("All Whatsapp templates must be configured before creating the sign request.")
                )

    @api.depends('request_item_ids')
    def _compute_signers_name(self):
        for sign_request in self:
            names = sign_request.request_item_ids.mapped('display_name')
            if self.env['sign.request.item']._check_whatsapp_template_exists():
                template_id = self.env['ir.config_parameter'].sudo().get_param(
                    'whatsapp_sign.whatsapp_completion_template_id'
                )
                template = self.env['whatsapp.template'].browse(int(template_id))
                sign_request.signers_name = format_list(
                    self.env, names, lang_code=template.lang_code
                )
            else:
                sign_request.signers_name = ', '.join(names)

    @api.depends('sign_log_ids', 'state')
    def _compute_refuser_partner(self):
        canceled_requests = self.filtered(lambda r: r.state == 'canceled')
        refusal_logs = self.env['sign.log']._read_group([
            ('sign_request_id', 'in', canceled_requests.ids),
            ('action', '=', 'refuse'),
        ], ['sign_request_id'], aggregates=['id:recordset'])
        logs_per_request = dict(refusal_logs)

        for sign_request in self:
            refusal_log = logs_per_request.get(sign_request, self.env['sign.log'])
            sign_request.refuser_partner = refusal_log.sign_request_item_id.partner_id

    @api.depends('message')
    def _compute_raw_optional_message(self):
        for sign_request in self:
            raw_html = sign_request.message
            sign_request.raw_optional_message = tools.html2plaintext(raw_html) if raw_html else "-"

    def _send_completed_documents_message(self, signers, request_edited, partner, access_token=None, with_message_cc=True, force_send=False, sign_request_item=None):
        """ Sends a completion message for a signed document.
        This method handles sending a completion message to the signers after a document has been fully signed.
        It primarily attempts to use a WhatsApp channel if configured.
        If the channel is 'whatsapp' and the required WhatsApp template is not found, it falls back to sending an email by calling the parent method.

        :param signers: The list of `res.partner` records to whom the completion message should be sent
        :param bool request_edited: A boolean indicating if the signing request was edited
        :param partner: The `res.partner` record of the main partner involved in the request
        :param str access_token: An optional access token for the request, if applicable
        :param bool with_message_cc: A boolean to include a carbon copy recipient in the message, if applicable
        :param bool force_send: A boolean to force the message to be sent immediately, bypassing any scheduled cron jobs
        :param sign_request_item: The `sign.request.item` record representing the specific item that the completion message will be sent to its partner
        :return: The result of the parent method if the message is sent via a different channel, otherwise `None`
        """
        self.ensure_one()

        is_whatsapp = self.send_channel == 'whatsapp'
        misconfiguration = is_whatsapp and not self.env['sign.request.item']._check_whatsapp_template_exists()
        if misconfiguration:
            self.send_channel = 'email'
        if misconfiguration or not is_whatsapp:
            return super()._send_completed_documents_message(signers, request_edited, partner,
                                                             access_token, with_message_cc, force_send)
        elif not sign_request_item:
            return

        template_id = self.env['ir.config_parameter'].sudo().get_param('whatsapp_sign.whatsapp_completion_template_id')
        whatsapp_template = self.env['whatsapp.template'].browse(int(template_id))
        whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': sign_request_item.id}).create({
            'wa_template_id': whatsapp_template.id,
            'res_model': 'sign.request.item'
        })
        whatsapp_composer.sudo()._send_whatsapp_template(force_send_by_cron=not force_send)

    def _send_refused_message(self, refuser, refusal_reason, partner, access_token=None, force_send=False, sign_request_item=None):
        """ Sends a refusal message for a document signing request.
        This method handles notifying relevant parties that a document signing request has been refused by one of the signers.

        :param refuser: The `res.partner` record of the person who refused the document
        :param str refusal_reason: The reason for the refusal as a string
        :param partner: The `res.partner` record of the main partner involved in the request
        :param str access_token: An optional access token for the request, if applicable
        :param bool force_send: A boolean to force the message to be sent immediately, bypassing any scheduled jobs
        :param sign_request_item: The `sign.request.item` record representing the specific item that the refusal message will be sent to its partner
        :return: The result of the parent method if the message is sent via a different channel, otherwise `None`
        """
        self.ensure_one()

        is_whatsapp = self.send_channel == 'whatsapp'
        misconfiguration = is_whatsapp and not self.env['sign.request.item']._check_whatsapp_template_exists()
        if misconfiguration:
            self.send_channel = 'email'
        if misconfiguration or not is_whatsapp:
            return super()._send_refused_message(refuser, refusal_reason, partner, access_token, force_send)
        elif not sign_request_item:
            return

        template_id = self.env['ir.config_parameter'].sudo().get_param('whatsapp_sign.whatsapp_refusal_template_id')
        whatsapp_template = self.env['whatsapp.template'].browse(int(template_id))
        self.refusal_reason = refusal_reason

        whatsapp_composer = self.env['whatsapp.composer'].with_context({'active_id': sign_request_item.id}).create({
            'wa_template_id': whatsapp_template.id,
            'res_model': 'sign.request.item'
        })
        whatsapp_composer.sudo()._send_whatsapp_template(force_send_by_cron=not force_send)
