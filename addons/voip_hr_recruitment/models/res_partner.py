from odoo import models
from odoo.exceptions import AccessError

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _voip_get_store_fields(self):
        def can_read_applicant_ids(partner):
            try:
                partner.fetch(["applicant_ids"])
            except AccessError:
                return False
            else:
                return True

        return [
            *super()._voip_get_store_fields(),
            Store.Many("applicant_ids", [Store.One("partner_id", []), "partner_name"], predicate=can_read_applicant_ids),
        ]
