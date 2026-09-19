from odoo import models

from odoo.addons.mail.tools.discuss import Store


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner"]

    def get_view_opportunities_action(self, phone=None):
        """
        Returns the action to view all opportunities of a partner.
        If the partner has no opportunities, it returns the action to create a new opportunity.
        If the partner has one opportunity, it returns the action to view the form view of the opportunity.
        If the partner has multiple opportunities, it returns the action to view all opportunities.
        """
        action = self.env["ir.actions.act_window"]._for_xml_id("crm.crm_lead_opportunities")
        if not self:  # If no partner is provided, we create a new opportunity for the phone.
            action["views"] = [[False, "form"]]
            action["context"] = {
                "default_phone": phone,
            }
            return action
        self.ensure_one()
        action["context"] = {
            "search_default_filter_won": True,
            "search_default_filter_ongoing": True,
            "search_default_filter_lost": True,
            "active_test": False,
        }
        if self.opportunity_count == 0:
            action["views"] = [[False, "form"]]
            action["context"]["default_partner_id"] = self.id
            return action
        domain = self._get_contact_opportunities_domain()
        if self.opportunity_count == 1:
            action["views"] = [[False, "form"]]
            action["res_id"] = self.env["crm.lead"].with_context(active_test=False).search(domain, limit=1).id
        else:
            action["domain"] = domain
        return action

    def _voip_get_store_fields(self):
        def can_read_opportunity_count(self):
            return self.env["crm.lead"].has_access("read")

        return [
            *super()._voip_get_store_fields(),
            Store.Attr("opportunity_count", predicate=can_read_opportunity_count),
        ]
