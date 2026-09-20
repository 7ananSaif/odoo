# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    @api.model
    def _load_pos_data_fields(self, config):
        params = super()._load_pos_data_fields(config)
        if config.company_id.country_code == 'DE':
            params += ['journal_id']
        return params
