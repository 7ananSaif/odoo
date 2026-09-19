from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def action_submit(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_cz_intrastat.cz_intrastat_goods_return_type':
            return self.env['l10n_cz_intrastat.intrastat.goods.submission.wizard']._open_submission_wizard(self)
        return super().action_submit()

    def _generate_locking_attachments(self, options):
        # Extends account_reports
        super()._generate_locking_attachments(options)
        if self.type_external_id == 'l10n_cz_intrastat.cz_intrastat_goods_return_type':
            self._add_attachment(self.type_id.report_id.dispatch_report_action(options, 'cz_intrastat_export_to_csv'))
