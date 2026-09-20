# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from collections import defaultdict

from odoo import models, api
from odoo.tools import partition


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        if self.env.company.country_id.code == "BR":
            data += ["l10n_latam.identification.type"]
        return data
