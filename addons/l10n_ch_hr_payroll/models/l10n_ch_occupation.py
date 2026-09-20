# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import fields, models


class L10nCHOccupation(models.Model):
    _name = 'l10n.ch.occupation'
    _description = "Swiss Employees Entry / Withdrawals"
    _auto = False

    employee_id = fields.Many2one('hr.employee', readonly=True)
    date_start = fields.Date('Entry in Company', readonly=True)
    date_end = fields.Date('Withdrawal from Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
            WITH ordered_contracts AS (
                SELECT
                    id,
                    contract_date_start,
                    contract_date_end,
                    employee_id,
                    LAG(contract_date_end) OVER (PARTITION BY employee_id ORDER BY contract_date_start) AS prev_end_date
                FROM hr_version
                WHERE contract_date_start IS NOT NULL
                      AND employee_id IS NOT NULL
            ),
            groups AS (
                SELECT
                    id,
                    contract_date_start,
                    contract_date_end,
                    employee_id,
                    CASE
                        WHEN prev_end_date IS NULL
                             OR prev_end_date <> contract_date_start - INTERVAL '1 day'
                        THEN 1
                        ELSE 0
                    END AS new_group
                FROM ordered_contracts
            ),
            group_ids AS (
                SELECT
                    id,
                    contract_date_start,
                    contract_date_end,
                    employee_id,
                    SUM(new_group) OVER (PARTITION BY employee_id ORDER BY contract_date_start) AS group_id
                FROM groups
            )
            SELECT
                MIN(id) AS id,
                MIN(contract_date_start) AS date_start,
                CASE
                    WHEN COUNT(*) > COUNT(contract_date_end) THEN NULL::date
                    ELSE MAX(contract_date_end)
                END AS date_end,
                employee_id
            FROM group_ids
            GROUP BY employee_id, group_id)
        """)
