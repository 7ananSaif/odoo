# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SignSendRequestSigner(models.TransientModel):
    _name = 'sign.send.request.signer'
    _description = 'Sign send request signer'

    role_id = fields.Many2one('sign.item.role', readonly=True)
    partner_id = fields.Many2one('res.partner', string="Contact")
    mail_sent_order = fields.Integer(string='Sign Order', default=1)
    sign_send_request_id = fields.Many2one('sign.send.request')
