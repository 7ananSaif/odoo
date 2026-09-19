import json

from odoo import models


class L10nFrIntrastatIntrastatSubmissionWizard(models.TransientModel):
    _name = 'l10n_fr_intrastat.intrastat.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Intrastat Submission Wizard"

    def action_proceed_with_submission(self):
        # EXTENDS account_reports
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        # If we come from account return, the wizard is not opened yet, so we open it here.
        if self.return_id.type_id.report_id == self.env.ref('account_intrastat.intrastat_report'):
            options['return_id'] = self.return_id.id
            return self.env['account.intrastat.goods.report.handler'].l10n_fr_intrastat_open_export_wizard(options)

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'l10n_fr_intrastat_services_export_to_xml',
                'no_closing_after_download': True,
            }
        }
