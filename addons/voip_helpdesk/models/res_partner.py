from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ticket_ids = fields.One2many("helpdesk.ticket", "partner_id")
    open_ticket_count = fields.Integer(compute="_compute_open_ticket_count")

    @api.depends("ticket_ids.fold")
    def _compute_open_ticket_count(self):
        def is_open(ticket):
            return not ticket.fold

        for partner in self:
            partner.open_ticket_count = len(partner.ticket_ids.filtered(is_open))
