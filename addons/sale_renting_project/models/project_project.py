# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _get_sale_orders_domain(self, all_sale_orders):
        domain = super()._get_sale_orders_domain(all_sale_orders)
        rental_filter = [('is_rental_order', '=', self.env.context.get('is_rental_order', False))]
        return Domain.AND([domain, rental_filter])

    def _get_view_action(self):
        if self.env.context.get('is_rental_order'):
            return self.env["ir.actions.act_window"]._for_xml_id("sale_renting.rental_order_action")
        return super()._get_view_action()
