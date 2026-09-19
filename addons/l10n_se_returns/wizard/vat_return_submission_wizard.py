import json

from odoo import models


class SwedishVatReturnXmlExport(models.TransientModel):
    _name = 'l10n_se_returns.vat.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Swedish VAT Return Submission Wizard"

    def action_proceed_with_submission(self):
        self.return_id.is_completed = True
        super().action_proceed_with_submission()

    def export_to_xml(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'l10n_se_export_tax_report_to_xml',
                'no_closing_after_download': True,
            }
        }
