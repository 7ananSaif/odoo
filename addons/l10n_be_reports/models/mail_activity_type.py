from odoo import fields, models


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    category = fields.Selection(selection_add=[
        ('ec_sales_list', 'EC Sales List'),
        ('partner_vat_listing_report', 'Partner VAT Listing Report'),
    ])
