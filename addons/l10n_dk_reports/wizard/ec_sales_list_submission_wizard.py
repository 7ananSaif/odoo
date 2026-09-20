import json
from odoo import models


class L10n_Dk_ReportsEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_dk_reports.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "EC Sales List Submission Wizard"

    def print_csv(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_sales_report_to_csv',
                'no_closing_after_download': True,
            },
        }

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id._mark_completed()
        super().action_proceed_with_submission()
