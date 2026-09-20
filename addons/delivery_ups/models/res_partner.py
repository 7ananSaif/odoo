# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    property_ups_carrier_account = fields.Char(string='UPS Account Number', company_dependent=True)
    bill_my_account = fields.Boolean(related='property_delivery_carrier_id.ups_bill_my_account')

    def _get_frontend_writable_fields(self):
        frontend_writable_fields = super()._get_frontend_writable_fields()
        frontend_writable_fields.add('property_ups_carrier_account')

        return frontend_writable_fields
