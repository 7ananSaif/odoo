from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def get_limited_partners_loading(self, offset=0):
        partner_ids = super().get_limited_partners_loading(offset)
        if (self.env.ref('l10n_ec.ec_final_consumer').id,) not in partner_ids:
            partner_ids.append((self.env.ref('l10n_ec.ec_final_consumer').id,))
        return partner_ids

    def _load_pos_data_read(self, records, config):
        data = super()._load_pos_data_read(records, config)
        if data and self.env.company.country_id.code == 'EC':
            final_consumer = self.env.ref('l10n_ec.ec_final_consumer', raise_if_not_found=False)
            data[0]['_final_consumer_id'] = final_consumer.id if final_consumer else None

        return data
