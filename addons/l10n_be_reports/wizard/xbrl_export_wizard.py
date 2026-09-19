import json

from odoo import fields, models


class XBRLExportWizard(models.TransientModel):
    _name = 'l10n_be_reports.xbrl.export.wizard'
    _description = "Belgian XBRL Export Wizard"

    last_deed_date = fields.Date(string="Date of last deed", required=True)

    def action_download_xbrl_file(self):
        options = self.env.context['options']
        options['last_deed_date'] = self.last_deed_date.strftime('%Y-%m-%d')
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'generate_xbrl_file',
            }
        }
