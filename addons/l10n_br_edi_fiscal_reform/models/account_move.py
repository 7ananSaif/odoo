# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_line_data_for_external_taxes(self):
        """ Override to set the operation_type per line. """
        res = super()._get_line_data_for_external_taxes()
        if not self.company_id.l10n_br_is_icbs:
            return res

        for line in res:
            line['cbs_ibs_deduction'] = line['base_line']['record'].l10n_br_cbs_ibs_deduction

        return res
