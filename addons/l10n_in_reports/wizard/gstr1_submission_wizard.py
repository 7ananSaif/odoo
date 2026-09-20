from odoo import models


class L10n_InGstr1SubmissionWizard(models.TransientModel):
    _name = 'l10n_in.gstr1.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Gstr1 Submission Wizard"

    def action_proceed_with_submission(self):
        """Override to handle GSTR-1 submission."""
        # Triggers cron to push gstr1 data and returns a notification about cron running in background
        return self.return_id.action_l10n_in_send_gstr1()
