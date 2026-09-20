from odoo import models


class PortalShare(models.TransientModel):
    _inherit = 'portal.share'

    def action_send_mail(self):
        # Extend portal share to subscribe partners when sharing helpdesk tickets.
        result = super().action_send_mail()

        # Only subscribe partners if shared from helpdesk.ticket
        if self.res_model == 'helpdesk.ticket':
            self.resource_ref.message_subscribe(partner_ids=self.partner_ids.ids)

        return result
