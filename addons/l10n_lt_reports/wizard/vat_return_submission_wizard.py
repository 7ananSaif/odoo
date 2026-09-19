import json

from odoo import models


class LithuanianReportsPeriodicVatXmlExport(models.TransientModel):
    _name = 'l10n_lt_reports.vat.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Lithuanian Periodic VAT Report Export Wizard"

    def print_xml(self):
        options = self.return_id._get_closing_report_options()
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_tax_report_to_xml',
                'no_closing_after_download': True,
            }
        }
