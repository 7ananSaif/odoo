# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['account.avatax.unique.code', 'sale.order']

    def _get_invoice_grouping_keys(self):
        res = super()._get_invoice_grouping_keys()
        if self.filtered('fiscal_position_id.is_avatax'):
            res += ['partner_shipping_id']
        return res

    def _get_avatax_service_params(self, commit=False):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._get_avatax_service_params(commit=commit)
        res.update({
            'document_type': 'SalesOrder',
            'document_date': self.date_order,
            'tax_date': self.date_order,
        })
        return res
