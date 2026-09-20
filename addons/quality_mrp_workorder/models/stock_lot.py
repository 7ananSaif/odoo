# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class StockLot(models.Model):
    _inherit = 'stock.lot'

    def _get_quality_check_domain(self, prod_lot):
        domain = super()._get_quality_check_domain(prod_lot)
        domain = Domain.OR([domain, [('finished_lot_ids', 'in', prod_lot.ids)]])
        return domain
