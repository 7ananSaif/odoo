from odoo import fields, models
from odoo.addons.l10n_mx_edi_extended.models.account_move import CUSTOM_NUMBERS_PATTERN


class StockLot(models.Model):
    _inherit = "stock.lot"

    l10n_mx_edi_landed_cost_id = fields.Many2one(
        comodel_name="stock.landed.cost",
        domain="[('state', '=', 'done')]",
        inverse="_inverse_l10n_mx_edi_landed_cost_id"
    )
    l10n_mx_edi_customs_number = fields.Char(related="l10n_mx_edi_landed_cost_id.l10n_mx_edi_customs_number")
    fiscal_country_codes = fields.Char(related="product_id.fiscal_country_codes")

    def _inverse_l10n_mx_edi_landed_cost_id(self):
        for lot in self:
            if not lot.product_id.l10n_mx_edi_can_use_customs_invoicing:
                continue
            split_name = lot.name.rsplit("/", 1)
            # If we already have a customs on the name we take only what is not, else we just take the whole name
            prefix_name = split_name[0].strip() if len(split_name) > 1 and CUSTOM_NUMBERS_PATTERN.match(split_name[1].strip()) else lot.name

            if prefix_name and lot.l10n_mx_edi_customs_number:
                lot.name = f"{prefix_name} / {lot.l10n_mx_edi_customs_number}"
            else:
                lot.name = prefix_name or lot.l10n_mx_edi_customs_number
