from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    intercompany_generate_sales_orders = fields.Boolean(string="Generate Sales order")
    intercompany_generate_purchase_orders = fields.Boolean(string="Generate Purchase Orders")
