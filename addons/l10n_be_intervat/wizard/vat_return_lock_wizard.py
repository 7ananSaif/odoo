from odoo import fields, models


class L10n_BeIntervatVatReturnLockWizard(models.TransientModel):
    _inherit = 'l10n_be_reports.vat.return.lock.wizard'

    is_rectification_needed = fields.Boolean(string="Rectification")
    rectification_ref = fields.Char(
        string="Reference",
        help="Reference of the declaration to correct (Declaration No. - VAT No. - Period) that is available in Intervat."
    )

    def _get_submission_options_to_inject(self):
        options = super()._get_submission_options_to_inject()
        if self.rectification_ref:
            options['rectification_ref'] = self.rectification_ref

        return options
