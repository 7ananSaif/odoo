# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('be', 'account.account')
    def _get_be_fiscal_accounts(self):
        return self._parse_csv('be', 'account.account', module='l10n_be_fiscal_categories')
