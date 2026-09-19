# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, modules
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('br', 'res.company')
    def _get_br_res_company_l10n_br_is_icbs(self):
        # Keep the setting by default for tests, otherwise mocked requests in l10n_br_{avatax,edi} won't match what's
        # being sent. We explicitly set it to True for tests in this module.
        return {
            self.env.company.id: {
                'l10n_br_is_icbs': not modules.module.current_test,
            }
        }
