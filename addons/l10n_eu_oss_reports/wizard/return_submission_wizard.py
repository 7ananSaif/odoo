from odoo import models, fields

import json


class L10nEuOssReportsSubmissionWizard(models.TransientModel):
    _name = 'l10n_eu_oss_reports.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "OSS Return Submission Wizard"

    country_code = fields.Char(related='return_id.company_id.account_fiscal_country_id.code')

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_to_xml',
                'no_closing_after_download': True,
            }
        }
