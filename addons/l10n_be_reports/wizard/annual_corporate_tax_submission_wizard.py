from odoo import models


class L10n_Be_ReportsPeriodicVatXmlExport(models.TransientModel):
    _name = 'l10n_be_reports.annual.corporate.tax.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Belgian Periodic VAT Report Export Wizard"

    def action_proceed_with_submission(self):
        self.return_id.is_completed = True
        super().action_proceed_with_submission()
