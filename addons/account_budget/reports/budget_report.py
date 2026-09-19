# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools import SQL


class BudgetReport(models.Model):
    _name = 'budget.report'
    _inherit = ['analytic.plan.fields.mixin']
    _description = "Budget Report"
    _auto = False
    _order = False

    date = fields.Date('Date')
    res_model = fields.Char('Model', readonly=True)
    res_id = fields.Many2oneReference('Document', model_field='res_model', readonly=True)
    description = fields.Char('Description', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', 'User', readonly=True)
    line_type = fields.Selection([('budget', 'Budget'), ('achieved', 'Achieved')], 'Type', readonly=True)
    budget = fields.Float('Budget', readonly=True)
    achieved = fields.Float('Achieved', readonly=True)
    theoretical = fields.Float(readonly=True)
    budget_analytic_id = fields.Many2one('budget.analytic', 'Budget Analytic', readonly=True)
    budget_line_id = fields.Many2one('budget.line', 'Budget Line', readonly=True)

    def _get_bl_query(self, plan_fnames):
        return SQL(
            """
            SELECT CONCAT('bl', bl.id::TEXT) AS id,
                   bl.budget_analytic_id AS budget_analytic_id,
                   bl.id AS budget_line_id,
                   'budget.analytic' AS res_model,
                   bl.budget_analytic_id AS res_id,
                   bl.date_from AS date,
                   bl.date_to AS bl_date_to,
                   ba.name AS description,
                   bl.company_id AS company_id,
                   NULL AS user_id,
                   'budget' AS line_type,
                   bl.budget_amount AS budget,
                   0 AS committed,  -- used in `account_budget_purchase`
                   0 AS achieved,
                   CASE WHEN NOW() < bl.date_to AND NOW() > bl.date_from
                        THEN (((NOW()::DATE - bl.date_from::DATE + 1))/(bl.date_to::DATE - bl.date_from::DATE + 1)::FLOAT)*bl.budget_amount
                        WHEN NOW() < bl.date_from
                        THEN 0
                        ELSE bl.budget_amount
                   END AS theoretical,
                   %(plan_fields)s
              FROM budget_line bl
              JOIN budget_analytic ba ON ba.id = bl.budget_analytic_id
            """,
            plan_fields=SQL(', ').join(self.env['budget.line']._field_to_sql('bl', fname) for fname in plan_fnames)
        )

    def _get_aal_query(self, plan_fnames):
        return SQL(
            """
            SELECT CONCAT('aal', aal.id::TEXT) AS id,
                   bl.budget_analytic_id AS budget_analytic_id,
                   bl.id AS budget_line_id,
                   'account.analytic.line' AS res_model,
                   aal.id AS res_id,
                   aal.date AS date,
                   bl.date_to AS bl_date_to,
                   aal.name AS description,
                   aal.company_id AS company_id,
                   aal.user_id AS user_id,
                   'achieved' AS line_type,
                   0 AS budget,
                   aal.amount * CASE WHEN ba.budget_type = 'expense' THEN -1 ELSE 1 END AS committed,  -- used in `account_budget_purchase`
                   aal.amount * CASE WHEN ba.budget_type = 'expense' THEN -1 ELSE 1 END AS achieved,
                   0 AS theoretical,
                   %(analytic_fields)s
              FROM account_analytic_line aal
         LEFT JOIN budget_line bl ON (bl.company_id IS NULL OR aal.company_id = bl.company_id)
                                 AND aal.date >= bl.date_from
                                 AND aal.date <= bl.date_to
                                 AND %(condition)s
         LEFT JOIN account_account aa ON aa.id = aal.general_account_id
         LEFT JOIN budget_analytic ba ON ba.id = bl.budget_analytic_id
             WHERE CASE
                       WHEN ba.budget_type = 'expense' THEN (
                           SPLIT_PART(aa.account_type, '_', 1) = 'expense'
                           OR (aa.account_type IS NULL AND aal.category NOT IN ('invoice', 'other'))
                           OR (aa.account_type IS NULL AND aal.category = 'other' AND aal.amount < 0)
                       )
                       WHEN ba.budget_type = 'revenue' THEN (
                           SPLIT_PART(aa.account_type, '_', 1) = 'income'
                           OR (aa.account_type IS NULL AND aal.category = 'other' AND aal.amount > 0)
                       )
                       ELSE TRUE
                   END
                   AND (SPLIT_PART(aa.account_type, '_', 1) IN ('income', 'expense') OR aa.account_type IS NULL)
            """,
            analytic_fields=SQL(', ').join(self.env['account.analytic.line']._field_to_sql('aal', fname) for fname in plan_fnames),
            condition=SQL(' AND ').join(SQL(
                "(%(bl)s IS NULL OR %(aal)s = %(bl)s)",
                bl=self.env['budget.line']._field_to_sql('bl', fname),
                aal=self.env['budget.line']._field_to_sql('aal', fname),
            ) for fname in plan_fnames)
        )

    @property
    def _table_query(self):
        self.env['account.move.line'].flush_model()
        self.env['budget.line'].flush_model()
        self.env['account.analytic.line'].flush_model()
        project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
        plan_fnames = [
            fname
            for plan in project_plan | other_plans
            if (fname := plan._column_name()) in self
        ]
        return SQL(
            "%s UNION ALL %s",
            self._get_bl_query(plan_fnames),
            self._get_aal_query(plan_fnames),
        )

    def action_open_reference(self):
        self.ensure_one()
        if self.res_model == 'account.analytic.line':
            analytical_line = self.env['account.analytic.line'].browse(self.res_id)
            if analytical_line.move_line_id:
                return analytical_line.move_line_id.action_open_business_doc()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'view_mode': 'form',
            'res_id': self.res_id,
        }
