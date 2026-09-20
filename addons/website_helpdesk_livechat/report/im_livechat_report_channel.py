# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import SQL


class Im_LivechatReportChannel(models.Model):
    _inherit = "im_livechat.report.channel"

    tickets_created = fields.Integer("Tickets created", aggregator="sum", readonly=True)

    def _select(self) -> SQL:
        return SQL("%s, helpdesk_ticket_data.tickets_created AS tickets_created", super()._select())

    def _from(self) -> SQL:
        return SQL(
            """%s
            LEFT JOIN LATERAL
                (
                    SELECT count(*) AS tickets_created
                      FROM helpdesk_ticket
                     WHERE helpdesk_ticket.origin_channel_id = C.id
                ) AS helpdesk_ticket_data ON TRUE
            """,
            super()._from(),
        )
