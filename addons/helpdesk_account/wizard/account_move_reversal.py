from odoo import Command, api, fields, models


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    @api.model
    def _get_default_so_domain(self, ticket):
        return [('partner_id', '=', ticket.partner_id.id), ('state', '=', 'sale'), ('invoice_ids.state', '=', 'posted'), ('invoice_ids.move_type', '=', 'out_invoice')]

    @api.model
    def _get_default_moves_domain(self, ticket):
        return [('state', '=', 'posted'), ('move_type', '=', 'out_invoice'), ('reversal_move_ids', '=', False)]

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        ticket_id = result.get('helpdesk_ticket_id')
        if ticket_id:
            if 'reason' in fields:
                result['reason'] = self.env._('Helpdesk Ticket #%s', ticket_id)
            # set default Invoice
            ticket = self.env['helpdesk.ticket'].browse(ticket_id)
            domain = self._get_default_so_domain(ticket)
            last_so = self.env['sale.order'].search(domain, limit=1, order='date_order desc')
            if last_so:
                result['helpdesk_sale_order_id'] = last_so.id
                moves = last_so.invoice_ids.filtered_domain(self._get_default_moves_domain(ticket))
                if moves:
                    result['move_ids'] = [Command.set(moves.ids)]
        return result

    # Add compute method
    move_ids = fields.Many2many('account.move', 'account_move_reversal_move', 'reversal_id', 'move_id',
        compute="_compute_move_ids", readonly=False, store=True, required=False)
    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', export_string_translation=False)
    helpdesk_sale_order_id = fields.Many2one('sale.order', string='Sales Order', domain="[('id', 'in', suitable_sale_order_ids)]")
    suitable_move_ids = fields.Many2many('account.move', compute='_compute_suitable_moves', export_string_translation=False)
    suitable_sale_order_ids = fields.Many2many('sale.order', compute='_compute_suitable_sale_orders', export_string_translation=False)

    @api.depends('helpdesk_sale_order_id')
    def _compute_move_ids(self):
        for r in self.filtered('helpdesk_sale_order_id'):
            r.move_ids = r.helpdesk_sale_order_id.invoice_ids.filtered(lambda move: move.state == 'posted' and move.move_type == 'out_invoice' and not move.reversal_move_ids)

    def _get_suitable_move_domain(self):
        self.ensure_one()
        domain = [('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]
        if self.helpdesk_ticket_id.partner_id:
            domain.append(('partner_id', 'child_of', self.helpdesk_ticket_id.partner_id.commercial_partner_id.id))
        if self.helpdesk_sale_order_id:
            invoice_ids = self.helpdesk_sale_order_id.invoice_ids.filtered(
                lambda inv: inv.amount_total > sum(
                    reversal_move.amount_total for reversal_move in inv.reversal_move_ids if reversal_move.state in ('draft', 'posted')
                )
            )
            if invoice_ids:
                domain.append(('id', 'in', invoice_ids.ids))
        return domain

    @api.depends('helpdesk_ticket_id.sale_order_id.invoice_ids', 'helpdesk_ticket_id.partner_id.commercial_partner_id', 'helpdesk_sale_order_id')
    def _compute_suitable_moves(self):
        for r in self:
            domain = r._get_suitable_move_domain()
            r.suitable_move_ids = self.env['account.move'].search(domain)

    @api.depends('move_ids')
    def _compute_journal_id(self):
        records_with_no_move = self.filtered(lambda record: not record.move_ids and not record.journal_id)
        for record in records_with_no_move:
            record.journal_id = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', record.company_id.id)], limit=1)
        super(AccountMoveReversal, self - records_with_no_move)._compute_journal_id()

    def _get_suitable_so_domain(self):
        self.ensure_one()
        domain = [('state', '=', 'sale'), ('invoice_ids.state', '=', 'posted'), ('invoice_ids.move_type', '=', 'out_invoice')]
        if self.helpdesk_ticket_id.partner_id:
            domain += [('partner_id', 'child_of', self.helpdesk_ticket_id.partner_id.commercial_partner_id.id)]
        return domain

    @api.depends('helpdesk_ticket_id.partner_id.commercial_partner_id')
    def _compute_suitable_sale_orders(self):
        for r in self:
            domain = r._get_suitable_so_domain()
            r.suitable_sale_order_ids = self.env['sale.order'].search(domain)

    def reverse_moves(self, is_modify=False):
        # OVERRIDE
        if not self.move_ids:
            lang = self.helpdesk_ticket_id.partner_id.lang or self.env.lang
            res = {
                'name': self.env._('Reverse Moves'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'context': {
                    'default_move_type': 'out_refund',
                    'default_partner_id': self.helpdesk_ticket_id.partner_id.id,
                    'default_date': fields.Date.context_today(self),
                    'default_journal_id': self.journal_id.id,
                    'default_ticket_id': self.helpdesk_ticket_id.id,
                    'default_ref': self.with_context(lang=lang).env._('Reversal of: %(reason)s', reason=self.reason),
                },
            }
        else:
            res = super().reverse_moves(is_modify=is_modify)

        if self.helpdesk_ticket_id:
            self.helpdesk_ticket_id.invoice_ids |= self.new_move_ids
            message = self.env._('Refund created')
            subtype_id = self.env['ir.model.data']._xmlid_to_res_id('helpdesk_account.mt_ticket_refund_created')
            for move_id in self.new_move_ids:
                move_id.message_post_with_source(
                    'helpdesk.ticket_creation',
                    render_values={'self': move_id, 'ticket': self.helpdesk_ticket_id},
                    subtype_id=subtype_id,
                )
                self.helpdesk_ticket_id.message_post_with_source(
                    'helpdesk.ticket_conversion_link',
                    render_values={'created_record': move_id, 'message': message},
                    subtype_id=subtype_id,
                )

        return res

    @api.constrains('journal_id', 'move_ids')
    def _check_journal_type(self):
        return super(AccountMoveReversal, self.filtered('move_ids'))._check_journal_type()

    def _prepare_default_reversal(self, move):
        res = super()._prepare_default_reversal(move)
        if self.helpdesk_ticket_id:
            res['ticket_id'] = self.helpdesk_ticket_id.id
        return res
