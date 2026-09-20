from odoo import models, api


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _l10n_es_get_report_modelo_number(self):
        self.ensure_one()
        xmlid_to_modelo = {
            "l10n_es_reports_2025.es_mod111_tax_return_type": 111,
            "l10n_es_reports_2025.es_mod115_tax_return_type": 115,
            "l10n_es_reports_2025.es_mod130_tax_return_type": 130,
            "l10n_es_reports_2025.es_mod347_tax_return_type": 347,
            "l10n_es_reports_2025.es_mod349_tax_return_type": 349,
            "l10n_es_reports_2025.es_mod390_tax_return_type": 390,
        }
        return xmlid_to_modelo.get(self.type_external_id, None) or super()._l10n_es_get_report_modelo_number()

    def action_submit(self):
        # EXTENDS account_reports
        mod_number = self._l10n_es_get_report_modelo_number()
        if mod_number:
            return self.env[f'l10n_es_reports_2025.mod{mod_number}.submission.wizard']._open_submission_wizard(self)
        return super().action_submit()


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.depends('report_id')
    def _compute_report_return_type(self):
        # EXTENDS account_reports
        # In Spain, only the mod303 (tax report), mod111 and mod115 (withholdings) should generate a tax closing entry.
        # Other reports (347, 349, 390...) are for information purposes only.
        # Ideally, these other reports would not inherit from generic_tax_report--> to be implemented after v19
        super()._compute_report_return_type()

        no_closing_es_report_xmlids = (
            'l10n_es_reports_2025.es_mod130_tax_return_type',
            'l10n_es_reports_2025.es_mod347_tax_return_type',
            'l10n_es_reports_2025.es_mod349_tax_return_type',
            'l10n_es_reports_2025.es_mod390_tax_return_type',
        )
        external_id_per_type = self.get_external_id()
        for record in self:
            if external_id_per_type.get(record.id) in no_closing_es_report_xmlids:
                record.is_tax_return_type = False
