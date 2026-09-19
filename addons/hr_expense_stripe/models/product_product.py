from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class ProductProduct(models.Model):
    _inherit = 'product.product'

    stripe_mcc_ids = fields.One2many(
        comodel_name='product.mcc.stripe.tag',
        inverse_name='product_id',
        string="Merchant Category Code (MCC)",
        help="For expenses created through Stripe Expense Cards, this Expense Category will be automatically assigned when a transaction "
             "matching the following MCC code occurs.\n Each MCC code can be linked to only one Expense Category."
    )

    stripe_issuing_activated = fields.Boolean(compute='_compute_stripe_issuing_activated')

    @api.depends_context('company')
    @api.depends('company_id')
    def _compute_stripe_issuing_activated(self):
        for product in self:
            product.stripe_issuing_activated = (product.company_id or self.env.company).stripe_issuing_activated

    @api.constrains('standard_price')
    def _check_no_cost_if_stripe_mcc(self):
        for product in self:
            price_precision = self.env['decimal.precision'].precision_get("Product Price")
            if not float_is_zero(product.standard_price, price_precision) and product.stripe_mcc_ids:
                raise ValidationError(_("You cannot set a cost on a product that is used as an Expense card category. Please duplicate it instead."))
