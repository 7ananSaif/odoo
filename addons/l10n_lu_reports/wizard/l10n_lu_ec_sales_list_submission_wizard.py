from odoo import _, models


class L10nLuEcSalesListSubmissionWizard(models.TransientModel):
    _name = 'l10n_lu_reports.ec.sales.list.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = 'EC Sales List Submission Wizard'

    def export_xml(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Export'),
            'view_mode': 'form',
            'res_model': 'l10n_lu.generate.vat.intra.report',
            'target': 'new',
            'views': [[self.env.ref('l10n_lu_reports.view_l10n_lu_generate_vat_intra_report').id, 'form']],
            'context': {**self.env.context, 'report_generation_options': self.return_id._get_closing_report_options()},
        }
