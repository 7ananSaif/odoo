# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Domain


class L10nUsW2(models.Model):
    _inherit = 'l10n.us.w2'

    def _get_allowed_payslips_domain(self):
        self.ensure_one()
        return Domain.AND([
            super()._get_allowed_payslips_domain(),
            [('move_id', '!=', False)],
        ])
