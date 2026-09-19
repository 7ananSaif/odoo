# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    ticket_id = fields.Many2one('helpdesk.ticket', export_string_translation=False, readonly=True)

    def write(self, vals):
        for move in self:
            if move.move_type == 'out_refund' and move.ticket_id and 'invoice_line_ids' not in vals and not move.invoice_line_ids:
                raise UserError(self.env._('You cannot create a Credit Note without invoice lines'))

        previous_states = None
        if 'state' in vals:
            previous_states = {move: move.state for move in self}
        res = super().write(vals)
        if 'state' in vals and vals['state'] in ('posted', 'cancel'):
            tracked_moves = self.filtered(lambda m: m.state != previous_states[m])
            ticket_ids = self.env['helpdesk.ticket'].sudo().search([
                ('use_credit_notes', '=', True), ('invoice_ids', 'in', tracked_moves.ids)])
            if ticket_ids:
                mapped_data = dict()
                for ticket in ticket_ids:
                    mapped_data[ticket] = (ticket.invoice_ids & self)
                for ticket, invoices in mapped_data.items():
                    if not invoices:
                        continue
                    subtype_id = self.env.ref('helpdesk.mt_ticket_refund_status', raise_if_not_found=False)
                    if not subtype_id:
                        continue
                    state_desc = dict(self._fields['state']._description_selection(self.env))[invoices[0].state].lower()
                    body = Markup('<br/>').join(
                        invoice._get_html_link() + invoice.env._('Refund %(status)s', status=state_desc)
                        for invoice in invoices
                    )
                    ticket.message_post(subtype_id=subtype_id.id, body=body)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.ticket_id and move.move_type == 'out_refund':
                move.ticket_id.invoice_ids |= move
                move.ticket_id.message_post_with_source(
                    'helpdesk.ticket_conversion_link',
                    render_values={'created_record': move, 'message': self.env._('Refund created')},
                    subtype_id=self.env['ir.model.data']._xmlid_to_res_id('helpdesk_account.mt_ticket_refund_created'),
                )
        return moves

    def action_view_helpdesk_ticket(self):
        self.ensure_one()
        """ Open the linked helpdesk ticket from the credit note form view. """
        return {
            'type': 'ir.actions.act_window',
            'name': self.ticket_id.name,
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
