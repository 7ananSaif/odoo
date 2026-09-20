from odoo import models, api
from collections import defaultdict

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        if self.env.user.has_group('account.group_account_readonly') or self.env.user.has_group('account.group_account_invoice'):
            data += ['account.move']
        data += ['ir.ui.view']
        return data

    def _reconcile_account_move_lines(self, data):
        data = super()._reconcile_account_move_lines(data)
        # Get pay later move lines created in the session (from POS orders not invoiced)
        pay_later_move_lines = data.get('pay_later_move_lines')

        # Add lines from invoiced orders that have been settled during this session
        pay_later_move_lines |= self.order_ids.mapped('lines').filtered(
            lambda l: (l.settled_invoice_id or l.settled_order_id) and l.order_id.account_move
        ).mapped('order_id.payment_ids.account_move_id.line_ids').filtered(
            lambda l: l.account_id == l.partner_id.property_account_receivable_id and not l.reconciled
        )

        if pay_later_move_lines:
            partner_account_lines = defaultdict(list)
            for move_line in pay_later_move_lines:
                key = (move_line.partner_id.id, move_line.account_id.id)
                partner_account_lines[key] += move_line
            all_session_move_lines = self.order_ids.lines.settled_order_id.session_id.move_id.line_ids
            all_invoice_move_lines = self.order_ids.lines.settled_invoice_id.line_ids

            for (partner_id, account_id), move_lines in partner_account_lines.items():
                session_move_lines = all_session_move_lines.filtered(
                    lambda l: l.partner_id.id == partner_id
                    and l.account_id.id == account_id
                    and not l.reconciled
                    and l.parent_state == 'posted'
                )
                invoice_move_lines = all_invoice_move_lines.filtered(
                    lambda l: l.partner_id.id == partner_id
                    and l.account_id.id == account_id
                    and not l.reconciled
                    and l.parent_state == 'posted'
                )
                (self.env['account.move.line'].browse([l.id for l in move_lines]) | session_move_lines | invoice_move_lines).reconcile()
        return data
