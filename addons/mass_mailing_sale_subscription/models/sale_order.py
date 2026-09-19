# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class SaleOrder(models.Model):
    _inherit = "sale.order"
    _mailing_enabled = True

    def _mailing_get_default_domain(self, mailing):
        domain = super()._mailing_get_default_domain(mailing)
        return Domain.AND([domain, [('subscription_state', '=', '3_progress')]])
