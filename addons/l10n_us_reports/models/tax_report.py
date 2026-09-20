from odoo import models


class L10nUSTaxreportHandler(models.AbstractModel):
    _name = 'l10n_us.tax.report.handler'
    _inherit = 'account.generic.tax.report.handler'
    _description = "US Tax Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        # Restrict the content of the generic tax report to US taxes only
        options.setdefault('forced_domain', []).extend([
            '|',
            ('tax_ids.country_id', 'in', report.country_id.ids),
            ('tax_line_id.country_id', 'in', report.country_id.ids),
        ])
