from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.addons.l10n_ke_edi_oscu.tests.test_live import TestKeEdi


class CommonPosKeEdiTest(CommonPosTest):
    @classmethod
    @TestKeEdi.setup_country('ke')
    def setUpClass(self):
        super().setUpClass()

        self.ke_edi_edit_product_template(self)
        self.ke_edi_edit_partners(self)

        self.warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_data['company'].id)], limit=1)
        self.stock_location = self.warehouse.lot_stock_id
        self.env['stock.quant'].create({
            'product_id': self.twenty_dollars_with_10_incl.product_variant_id.id,
            'location_id': self.stock_location.id,
            'quantity': 20.0,
        })

    def ke_edi_edit_partners(self):
        self.partner_moda = self.env['res.partner'].create({
            'name': 'Ralph Jr',
            'street': 'The Cucumber Lounge',
            'city': 'Vineland',
            'zip': '00500',
            'vat': 'A000123456F',
            'country_id': self.env.ref('base.ke').id,
        })

    def ke_edi_edit_product_template(self):
        unspsc_code = self.env['product.unspsc.code'].search([('code', '=', '52161557')], limit=1)
        oscu_code = self.env['l10n_ke_edi_oscu.code'].search([('code', '=', 'BA')], limit=1)
        self.twenty_dollars_with_10_incl.write({
            'type': 'consu',
            'is_storable': True,
            'unspsc_code_id': unspsc_code.id,
            'l10n_ke_product_type_code': '2',
            'l10n_ke_packaging_unit_id': oscu_code.id,
            'l10n_ke_origin_country_id': self.env.ref('base.be').id,
            'l10n_ke_packaging_quantity': 2,
            'standard_price': 30,
            'taxes_id': self.tax_sale_a.ids
        })
