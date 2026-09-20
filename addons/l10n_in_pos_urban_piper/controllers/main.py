from odoo.addons.pos_urban_piper.controllers.main import PosUrbanPiperController
from odoo.fields import Domain
from odoo.http import request


class PosUrbanPiperInController(PosUrbanPiperController):

    def _get_tax_value(self, taxes_data, pos_config):
        taxes = super()._get_tax_value(taxes_data, pos_config)
        if pos_config.company_id.country_id.code == 'IN' and taxes:
            parent_tax = request.env['account.tax'].sudo().search([('children_tax_ids', 'in', taxes.ids)])
            if parent_tax:
                taxes = parent_tax
        return taxes

    def _get_tax_domain(self, pos_config, tax_percentage):
        domain = super()._get_tax_domain(pos_config, tax_percentage)
        if pos_config.company_id.country_id.code == "IN":
            domain &= Domain("tax_group_id.name", "=", "GST")
        return domain
