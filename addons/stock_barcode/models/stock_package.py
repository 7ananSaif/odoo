# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class StockPackage(models.Model):
    _inherit = 'stock.package'
    _barcode_field = 'name'

    @api.model
    def _search(self, domain, *args, **kwargs):
        domain = self.env.company.nomenclature_id._preprocess_gs1_search_args(domain, ['package'], 'name')
        return super()._search(domain, *args, **kwargs)

    @api.model
    def action_create_from_barcode(self, vals_list):
        """ Creates a new package then returns its data to be added in the client side cache.
        """
        res = self.create(vals_list)
        return {
            'stock.package': res.read(self._get_fields_stock_barcode(), False)
        }

    @api.model
    def _get_fields_stock_barcode(self):
        return [
            'name',
            'complete_name',
            'dest_complete_name',
            'location_id',
            'location_dest_id',
            'package_dest_id',
            'parent_package_id',
            'outermost_package_id',
            'package_type_id',
            'contained_quant_ids',
        ]

    @api.model
    def _get_usable_packages(self):
        usable_packages_domain = [
            '|',
            ('package_type_id.package_use', '=', 'reusable'),
            ('location_id', '=', False),
        ]
        # Limit the number of records to load if param is set.
        records_limit = int(self.env['ir.config_parameter'].sudo().get_param('stock_barcode.usable_packages_limit'))
        packages = self.env['stock.package'].search(usable_packages_domain, limit=records_limit, order='create_date desc')
        loc_ids = self.env.context.get('pack_locs')
        if loc_ids:
            packages |= self.env['stock.package'].search([('location_id', 'in', loc_ids)])
        return packages
