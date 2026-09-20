import json

from odoo import models


class SwedishEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_se_returns.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Swedish EC Sales List Submission Wizard"

    def action_proceed_with_submission(self):
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def export_to_kvr(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_sales_report_to_kvr',
                'no_closing_after_download': True,
            }
        }
