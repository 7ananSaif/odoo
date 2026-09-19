# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'
    _barcode_field = 'barcode'

    barcode_img = fields.Binary(compute="_compute_barcode_img")

    @api.depends('barcode')
    def _compute_barcode_img(self):
        options = {
            'width': 300,
            'height': 100,
            'humanreadable': True
        }
        for location in self:
            if location.barcode:
                try:
                    barcode = self.env['ir.actions.report'].barcode(
                        'Code128',
                        location.barcode,
                        **options
                    )
                    location.barcode_img = base64.b64encode(barcode).decode()
                except ValueError:
                    location.barcode_img = False
                    pass
            else:
                location.barcode_img = False

    @api.model
    def _search(self, domain, *args, **kwargs):
        domain = self.env.company.nomenclature_id._preprocess_gs1_search_args(domain, ['location', 'location_dest'])
        return super()._search(domain, *args, **kwargs)

    @api.model
    def _get_fields_stock_barcode(self):
        return ['barcode', 'display_name', 'name', 'parent_path', 'usage']

    def get_counted_quant_data_records(self):
        self.ensure_one()
        return self.quant_ids.get_stock_barcode_data_records()
