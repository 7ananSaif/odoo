import json

from odoo import models


class LithuanianEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_lt_reports.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Lithuanian EC Sales List Submission Wizard'

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def export_to_xlsx(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_to_xlsx',
                'no_closing_after_download': True,
            }
        }
