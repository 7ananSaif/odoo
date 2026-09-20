from odoo import api, fields, models


class RatingRating(models.Model):
    _inherit = 'rating.rating'

    ticket_id = fields.Many2one('helpdesk.ticket', compute='_compute_ticket_id', search='_search_ticket_id')

    @api.depends('res_id', 'res_model')
    def _compute_ticket_id(self):
        if self.env['helpdesk.team'].search_count([('use_rating', '=', True)], limit=1):
            if helpdesk_ratings := self.filtered(lambda r: r.res_model == 'helpdesk.ticket' and r.res_id):
                helpdesk_tickets = self.env['helpdesk.ticket'].search([('id', 'in', helpdesk_ratings.mapped('res_id'))])
                ticket_map = {ticket.id: ticket for ticket in helpdesk_tickets}

                for helpdesk_rating in helpdesk_ratings:
                    helpdesk_rating.ticket_id = ticket_map.get(helpdesk_rating.res_id, False)
            (self - helpdesk_ratings).ticket_id = False
        else:
            self.ticket_id = False

    def _search_ticket_id(self, operator, value):
        ticket_ids = self.env['helpdesk.ticket']._search([('id', operator, value)])
        return [('res_model', '=', 'helpdesk.ticket'), ('res_id', 'in', ticket_ids)]
