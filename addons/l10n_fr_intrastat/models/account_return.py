from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # EXTENDS account_reports
        if self.type_external_id in {
            'l10n_fr_intrastat.l10n_fr_intrastat_goods_return_type',
            'l10n_fr_intrastat.l10n_fr_intrastat_services_return_type',
        }:
            return self.env['l10n_fr_intrastat.intrastat.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()
