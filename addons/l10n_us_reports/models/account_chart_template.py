from odoo.addons.account.models.chart_template import template
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('us', 'res.company')
    def _get_us_reports_res_company(self):
        return {
            self.env.company.id: {
                'deferred_expense_account_id': 'account_account_us_prepaid_expenses',
                'deferred_revenue_account_id': 'account_account_us_deferred_revenue',
            }
        }
