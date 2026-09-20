# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools import SQL


class BudgetReport(models.Model):
    _inherit = 'budget.report'

    line_type = fields.Selection(selection_add=[('committed', 'Committed')])
    committed = fields.Float('Committed', readonly=True)

    def _get_pol_query(self, plan_fnames):
        precision_digits = self.env['decimal.precision'].precision_get('Product Unit')
        qty_invoiced_table = SQL(
            """
               SELECT SUM(
                          CASE WHEN COALESCE(uom_aml.id != uom_pol.id, FALSE)
                               THEN ROUND(CAST((aml.quantity / uom_aml.factor) * uom_pol.factor AS NUMERIC), %(precision_digits)s)
                               ELSE COALESCE(aml.quantity, 0)
                          END
                          * CASE WHEN am.move_type = 'in_invoice' THEN 1
                                 WHEN am.move_type = 'in_refund' THEN -1
                                 ELSE 0 END
                      ) AS qty_invoiced,
                      pol.id AS pol_id
                 FROM purchase_order po
            LEFT JOIN purchase_order_line pol ON pol.order_id = po.id
            LEFT JOIN account_move_line aml ON aml.purchase_line_id = pol.id
            LEFT JOIN account_move am ON aml.move_id = am.id
            LEFT JOIN uom_uom uom_aml ON uom_aml.id = aml.product_uom_id
            LEFT JOIN uom_uom uom_pol ON uom_pol.id = pol.product_uom_id
                WHERE aml.parent_state = 'posted'
             GROUP BY pol.id
        """,
        precision_digits=precision_digits
        )
        return SQL(
            """
            SELECT (pol.id::TEXT || '-' || ROW_NUMBER() OVER (PARTITION BY pol.id ORDER BY pol.id)) AS id,
                   bl.budget_analytic_id AS budget_analytic_id,
                   bl.id AS budget_line_id,
                   'purchase.order' AS res_model,
                   po.id AS res_id,
                   po.date_order AS date,
                   bl.date_to AS bl_date_to,
                   pol.name AS description,
                   pol.company_id AS company_id,
                   po.user_id AS user_id,
                   'committed' AS line_type,
                   0 AS budget,
                   COALESCE(pol.price_subtotal::FLOAT, pol.price_unit::FLOAT * pol.product_qty)
                        / COALESCE(NULLIF(pol.product_qty, 0), 1)
                        * (pol.product_qty - COALESCE(qty_invoiced_table.qty_invoiced, 0))
                        / po.currency_rate
                        * (a.rate)
                        * CASE WHEN ba.budget_type = 'both' THEN -1 ELSE 1 END AS committed,
                   0 AS achieved,
                   0 AS theoretical,
                   %(analytic_fields)s
              FROM purchase_order_line pol
         LEFT JOIN (%(qty_invoiced_table)s) qty_invoiced_table ON qty_invoiced_table.pol_id = pol.id
              JOIN purchase_order po ON pol.order_id = po.id AND po.state = 'purchase'
        CROSS JOIN JSONB_TO_RECORDSET(pol.analytic_json) AS a(rate FLOAT, %(field_cast)s)
         LEFT JOIN budget_line bl ON (bl.company_id IS NULL OR po.company_id = bl.company_id)
                                 AND po.date_order >= bl.date_from
                                 AND date_trunc('day', po.date_order) <= bl.date_to
                                 AND %(condition)s
         LEFT JOIN budget_analytic ba ON ba.id = bl.budget_analytic_id
             WHERE pol.product_qty > COALESCE(qty_invoiced_table.qty_invoiced, 0)
               AND ba.budget_type != 'revenue'
            """,
            analytic_fields=SQL(', ').join(self.env['account.analytic.line']._field_to_sql('a', fname) for fname in plan_fnames),
            qty_invoiced_table=qty_invoiced_table,
            field_cast=SQL(', ').join(SQL('%s FLOAT', SQL.identifier(fname)) for fname in plan_fnames),
            condition=SQL(' AND ').join(SQL(
                "(%(bl)s IS NULL OR %(a)s = %(bl)s)",
                bl=self.env['budget.line']._field_to_sql('bl', fname),
                a=self.env['budget.line']._field_to_sql('a', fname),
            ) for fname in plan_fnames)
        )

    @property
    def _table_query(self):
        self.env['purchase.order'].flush_model()
        self.env['purchase.order.line'].flush_model()
        project_plan, other_plans = self.env['account.analytic.plan']._get_all_plans()
        plan_fnames = [plan._column_name() for plan in project_plan | other_plans]
        return SQL(
            "%s UNION ALL %s",
            super()._table_query,
            self._get_pol_query(plan_fnames),
        )
