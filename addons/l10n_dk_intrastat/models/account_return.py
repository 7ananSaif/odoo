from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_dk_intrastat.dk_intrastat_goods_return_type':
            return self.env['l10n_dk_intrastat.intrastat.goods.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()
