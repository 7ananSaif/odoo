from odoo import models


class AccountReturn(models.Model):
    _inherit = 'account.return'

    def _get_vat_closing_entry_additional_domain(self):
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_external_id == 'l10n_uk_reports.uk_tax_return_type':
            purchase_tax_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_deduction')._get_matching_tags()
            sales_tax_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_deduction')._get_matching_tags()
            tags = purchase_tax_tags + sales_tax_tags
            # EXTENDS account_reports
            domain += [
                ('tax_tag_ids', 'not in', tags.ids),  # Exclude CIS taxes lines from tax closing.
            ]
        return domain
