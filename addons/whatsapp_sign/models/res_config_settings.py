# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    send_request_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Request template',
        config_parameter='whatsapp_sign.whatsapp_template_id',
        domain=[('model', '=', 'sign.request.item'), ('status', '=', 'approved')],
        default=lambda self: self.env.ref('whatsapp_sign.sign_request_whatsapp_template', raise_if_not_found=False),
        help="Choose an approved WhatsApp template to send signature requests"
    )

    request_completion_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Completed template',
        config_parameter='whatsapp_sign.whatsapp_completion_template_id',
        domain=[('model', '=', 'sign.request.item'), ('status', '=', 'approved')],
        default=lambda self: self.env.ref('whatsapp_sign.sign_request_completion_whatsapp_template', raise_if_not_found=False),
        help="Choose an approved WhatsApp template to send the signature request completion"
    )

    request_refusal_wa_template_id = fields.Many2one(
        'whatsapp.template',
        string='Refusal template',
        config_parameter='whatsapp_sign.whatsapp_refusal_template_id',
        domain=[('model', '=', 'sign.request.item'), ('status', '=', 'approved')],
        default=lambda self: self.env.ref('whatsapp_sign.sign_request_refusal_whatsapp_template', raise_if_not_found=False),
        help="Choose an approved WhatsApp template to send the signature request refusal"
    )
