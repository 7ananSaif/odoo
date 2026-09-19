# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountExternalTaxMixin(models.AbstractModel):
    _inherit = "account.external.tax.mixin"

    def _prepare_l10n_br_avatax_document_line_service_call(self, line_data, *args):
        # EXTENDS 'account.external.tax.mixin'
        res = super()._prepare_l10n_br_avatax_document_line_service_call(line_data, *args)
        res['itemCode'] = line_data['base_line']['product_id'].default_code
        return res
