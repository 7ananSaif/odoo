# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api
from odoo.tools import convert

class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _init_preparation_display_data(self):
        main_company = self.env.ref('base.main_company', raise_if_not_found=False)
        is_main_company = main_company and self.env.company.id == main_company.id
        if is_main_company:
            self._load_preparation_display_data()
            self._load_preparation_display_demo_data()

    def _load_preparation_display_data(self):
        if self.env.ref('pos_restaurant.pos_config_main_restaurant', raise_if_not_found=False) and not self.env.ref('pos_restaurant_preparation_display.preparation_display_main_restaurant', raise_if_not_found=False):
            convert.convert_file(self._env_with_clean_context(), 'pos_restaurant_preparation_display', 'data/main_restaurant_preparation_display_data.xml', idref=None, mode='init', noupdate=True)

    def _load_preparation_display_demo_data(self):
        if (self.env.ref('pos_restaurant_preparation_display.preparation_display_main_restaurant', raise_if_not_found=False) and not self.env.ref('pos_restaurant_preparation_display.preparation_display_order_0', raise_if_not_found=False)
                and self.env.ref('pos_restaurant.pos_closed_order_3_1', raise_if_not_found=False)):
            convert.convert_file(self._env_with_clean_context(), 'pos_restaurant_preparation_display', 'data/pos_restaurant_preparation_display_demo.xml', idref=None, mode='init', noupdate=True)

    @api.model
    def load_onboarding_restaurant_scenario(self, with_demo_data=True):
        res = super().load_onboarding_restaurant_scenario(with_demo_data)
        self._load_preparation_display_data()
        if with_demo_data:
            self._load_preparation_display_demo_data()
        return res

    def _load_restaurant_demo_data(self, with_demo_data=True):
        super()._load_restaurant_demo_data(with_demo_data)
        self._load_preparation_display_demo_data()
