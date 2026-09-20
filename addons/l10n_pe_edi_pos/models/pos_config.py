from odoo import models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _load_pos_data_read(self, records, config):
        data = super()._load_pos_data_read(records, config)
        if data:
            l10n_pe_edi_refund_reason = self.env['ir.model.fields']._get('account.move', 'l10n_pe_edi_refund_reason')
            data[0]['_l10n_pe_edi_refund_reason'] = [
                {'value': s.value, 'name': s.name}
                for s in l10n_pe_edi_refund_reason.selection_ids
            ]
        return data
