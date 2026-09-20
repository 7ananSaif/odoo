from odoo import models
from odoo.fields import Domain


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _get_audit_line_domain(self, column_group_options, expression, params):
        res = super()._get_audit_line_domain(column_group_options, expression, params)
        if expression.formula == '_report_custom_engine_total_disallowed_expenses':
            res = Domain.AND([res, [('account_id.fiscal_category_id.id', '!=', False)]])
        return res
