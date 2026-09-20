from odoo import models


class L10n_Hr_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_hr_reports.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "EC Sales List Submission Wizard"

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id._mark_completed()
        super().action_proceed_with_submission()
