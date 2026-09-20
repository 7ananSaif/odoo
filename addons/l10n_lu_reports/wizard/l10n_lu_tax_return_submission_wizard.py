from odoo import models


class L10nLuTaxReturnSubmissionWizard(models.TransientModel):
    _name = 'l10n_lu_reports.tax.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'Tax Return Submission Wizard'

    def export_xml(self):
        new_context = {
            **self.env.context,
            'report_generation_options': self.return_id._get_closing_report_options(),
        }
        return self.env['l10n_lu.generate.tax.report'].with_context(new_context).create({}).get_xml()
