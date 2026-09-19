from odoo import models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    def _get_vat_closing_entry_additional_domain(self):
        # EXTENDS account_reports
        domain = super()._get_vat_closing_entry_additional_domain()
        return_types = [
            'l10n_ca_reports.ca_gsthst_tax_return_type',
            'l10n_ca_reports.ca_pst_bc_tax_return_type',
            'l10n_ca_reports.ca_pst_mb_tax_return_type',
            'l10n_ca_reports.ca_qst_tax_return_type',
            'l10n_ca_reports.ca_pst_sk_tax_return_type',
        ]
        if self.type_external_id in return_types:
            tax_tags = self.type_id.report_id.line_ids.expression_ids._get_matching_tags()
            domain.append(('tax_tag_ids', 'in', tax_tags.ids))
        return domain
