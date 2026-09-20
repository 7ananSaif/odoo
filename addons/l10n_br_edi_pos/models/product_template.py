# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_br_pos_warning = fields.Text("Brazilian POS Warning", compute="_compute_l10n_br_pos_warning")

    @api.depends("available_in_pos", "sale_ok", "taxes_id")
    def _compute_l10n_br_pos_warning(self):
        for product in self:
            product.l10n_br_pos_warning = False
            if product.available_in_pos and product.sale_ok and not all(product.taxes_id.mapped("price_include")):
                product.l10n_br_pos_warning = _("Products with price-excluded taxes will not be loaded in NFC-e Point of Sales.")

    @api.model
    def _load_pos_data_domain(self, data, config):
        """Override."""
        domain = super()._load_pos_data_domain(data, config)
        if config.l10n_br_is_nfce:
            taxes_domain = [*self.env["account.tax"]._check_company_domain(config.company_id.id), ("price_include", "=", False)]
            domain = Domain.AND(
                [
                    domain,
                    [
                        (
                            "taxes_id",
                            "not any",
                            taxes_domain,
                        ),
                    ],
                    # Exclude combo products that have combo items with price-excluded taxes. _load_pos_data() of product.template
                    # will load combo products indiscriminately of the provided domain, thus bypassing our goal of not
                    # loading products with price-excluded taxes.
                    Domain.OR(
                        [
                            [("type", "!=", "combo")],
                            [("combo_ids.combo_item_ids.product_id.product_tmpl_id.taxes_id", "not any", taxes_domain)]
                        ],
                    ),
                ]
            )

        return domain
