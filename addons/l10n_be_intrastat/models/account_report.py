from odoo import models


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_variants(self, report_id):
        variants = super()._get_variants(report_id)
        if self.env.company.account_fiscal_country_id.code != 'BE':
            return variants

        # Generic service report is replaced by F01DGS or F02CMS report in belgium
        return variants - self.env.ref('account_intrastat.intrastat_report_services')
