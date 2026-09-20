import json
from odoo import models


class L10n_dk_IntrastatIntrastatGoodsSubmissionWizard(models.TransientModel):
    _name = 'l10n_dk_intrastat.intrastat.goods.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Intrastat Goods Submission Wizard'

    def action_proceed_with_submission(self):
        # Extends account_reports
        self.return_id.is_completed = True
        return super().action_proceed_with_submission()

    def print_xslx(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'dk_export_to_xlsx',
                'no_closing_after_download': True,
            },
        }
