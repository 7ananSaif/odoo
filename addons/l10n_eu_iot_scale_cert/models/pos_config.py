# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, release

from odoo.addons.l10n_eu_iot_scale_cert.controllers.checksum import calculate_scale_checksum
from odoo.addons.l10n_eu_iot_scale_cert.controllers.expected_checksum import EXPECTED_CHECKSUM


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if read_records:
            is_eu_country = self.env.company.country_id in self.env.ref('base.europe').country_ids
            kg_uom_id = self.env.ref('uom.product_uom_kgm').id
            unit_uom_id = self.env.ref('uom.product_uom_unit').id
            read_records[0]["_is_eu_country"] = is_eu_country
            read_records[0]["_kg_uom_id"] = kg_uom_id
            read_records[0]["_unit_uom_id"] = unit_uom_id
            if is_eu_country and config.iface_electronic_scale:
                read_records[0]["_scale_checksum"] = calculate_scale_checksum()[0]
                read_records[0]["_scale_checksum_expected"] = EXPECTED_CHECKSUM
                read_records[0]["_lne_certification_details"] = config._get_certification_details()
        return read_records

    @api.model
    def fix_rounding_for_scale_certification(self):
        decimal_precision = self.env.ref('uom.decimal_product_uom')
        if decimal_precision.digits < 3:
            decimal_precision.digits = 3
        if not self.env.user.has_group('uom.group_uom'):
            self.env['res.config.settings'].create({
                'group_uom': True,
            }).execute()

    def _get_certification_details(self):
        self.ensure_one()
        return {
            "pos_name": "Odoo Point of Sale",
            "odoo_version": release.major_version,
            "certificate_number": "LNE-40724",
            "pos_app_version": self.env["ir.module.module"]._get("point_of_sale").installed_version,
            "iot_image": self.iface_scale_id.iot_id.version,
        }
