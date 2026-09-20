import random

from odoo import _, api, models, fields
from odoo.exceptions import UserError, ValidationError


# https://docs.stripe.com/connect/setting-mcc#list
class ProductMCCSTripeTag(models.Model):
    _name = 'product.mcc.stripe.tag'
    _description = "Stripe MCC Tag"
    _order = 'code'

    name = fields.Char(string="Name", required=True, translate=True)
    stripe_name = fields.Char(string="Stripe Name", required=True, readonly=True)
    code = fields.Char(string="Code", required=True, readonly=True, size=4, copy=False, index='btree')
    product_id = fields.Many2one(
        string="Expense Category to use",
        comodel_name='product.product',
        domain=[('can_be_expensed', '=', True), ('standard_price', '=', 0)],
        company_dependent=True,
    )
    product_name = fields.Char(related='product_id.name', string="Product Name")
    color = fields.Integer(
        string="Color Index",
        default=lambda self: random.randint(0, 9),
        store=True,
    )

    _constraint_code_unique = models.Constraint(
        definition='unique(code)',
        message="The code of the MCC tag must be unique!",
    )

    @api.constrains('product_id')
    def _check_no_cost(self):
        price_precision = self.env['decimal.precision'].precision_get("Product Price")
        for product in self.product_id:
            if round(product.standard_price, int(price_precision)) != 0:
                raise ValidationError(_("To be used by Expense cards, the product '%(name)s' must have a cost of 0.00", name=product.name))

    def write(self, vals):
        if ('code' in vals or 'stripe_name' in vals) and not self.has_access('create'):
            raise UserError(_(
                "Only administrators can change the code or the stripe technical name of a MCC."
            ))
        return super().write(vals)
