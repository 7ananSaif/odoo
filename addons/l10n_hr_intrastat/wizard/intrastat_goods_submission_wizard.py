from odoo import models


class L10n_Hr_IntrastatIntrastatGoodsSubmissionWizard(models.TransientModel):
    _name = 'l10n_hr_intrastat.intrastat.goods.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Intrastat Goods Submission Wizard'

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        return super().action_proceed_with_submission()
