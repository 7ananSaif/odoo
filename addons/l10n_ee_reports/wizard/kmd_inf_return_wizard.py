
from odoo import models


class L10n_Ee_KMDINFReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_ee_reports.kmd.inf.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "KMD INF Return Submission Wizard"

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        return super().action_proceed_with_submission()
