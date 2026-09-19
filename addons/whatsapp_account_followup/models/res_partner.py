from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_followup_whatsapp_number(self):
        followup_contacts = (self._get_all_followup_contacts() | self).filtered(lambda partner: partner.phone)
        return followup_contacts[0].phone if followup_contacts else ''

    def _send_followup(self, options):
        super()._send_followup(options)
        followup_line = options.get('followup_line')
        if options.get('whatsapp', followup_line.send_whatsapp):
            self.send_followup_whatsapp(options)

    def send_followup_whatsapp(self, options):
        """
        Send a follow-up report by WhatsApp to customers in self
        """
        for partner in self:
            self.env['account.followup.report']._send_whatsapp(partner=partner, **options)
