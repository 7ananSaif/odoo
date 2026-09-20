# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def open_mpf_scheme_list(self):
        self.ensure_one()
        return self.env['l10n_hk.mpf.scheme'].search([])._get_records_action(name=self.env._("MPF Schemes"))
