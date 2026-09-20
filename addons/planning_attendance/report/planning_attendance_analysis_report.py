# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.sql import drop_view_if_exists, SQL


class PlanningAttendanceAnalysisReport(models.Model):
    _name = 'planning.attendance.analysis.report'

    _description = "Planning / Attendance Analysis"
    _auto = False
    _rec_name = "entry_date"
    _order = "entry_date desc"

    entry_date = fields.Date(readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    effective_hours = fields.Float("Attendance Time", readonly=True)
    planned_hours = fields.Float("Planned Time", readonly=True)
    time_difference = fields.Float("Time Difference", readonly=True)
    effective_costs = fields.Float("Attendance Cost", readonly=True)
    planned_costs = fields.Float("Planned Cost", readonly=True)
    cost_difference = fields.Float("Cost Difference", readonly=True)

    def init(self):
        query = """
        SELECT MAX(id) AS id,
               t.entry_date,
               t.employee_id,
               t.department_id,
               t.company_id,
               COALESCE(SUM(t.worked_hours), 0) AS effective_hours,
               COALESCE(SUM(t.allocated_hours), 0) AS planned_hours,
               COALESCE(SUM(t.worked_hours), 0) - COALESCE(SUM(t.allocated_hours), 0) AS time_difference,
               NULLIF(COALESCE(SUM(t.worked_hours), 0) * t.hourly_cost, 0) AS effective_costs,
               NULLIF(COALESCE(SUM(t.allocated_hours), 0) * t.hourly_cost, 0) AS planned_costs,
               NULLIF((COALESCE(SUM(t.worked_hours), 0) - COALESCE(sum(t.allocated_hours), 0)) * t.hourly_cost, 0) AS cost_difference
          FROM (
                   SELECT -A.id AS id,
                          A.check_in::date AS entry_date,
                          A.employee_id AS employee_id,
                          V.department_id AS department_id,
                          E.company_id AS company_id,
                          E.hourly_cost AS hourly_cost,
                          A.worked_hours AS worked_hours,
                          0.0 AS allocated_hours
                     FROM hr_attendance A
                LEFT JOIN hr_employee E ON E.id = A.employee_id
                LEFT JOIN (
                    SELECT DISTINCT ON (employee_id) *
                    FROM hr_version
                    ORDER BY employee_id, date_version DESC
                ) V ON V.employee_id = E.id
                UNION ALL
                   SELECT S.id AS id,
                          d::date AS entry_date,
                          S.employee_id AS employee_id,
                          V.department_id AS department_id,
                          S.company_id AS company_id,
                          E.hourly_cost AS hourly_cost,
                          0.0 AS worked_hours,
                          S.allocated_hours AS allocated_hours
                     FROM generate_series(
                            (SELECT min(start_datetime) FROM planning_slot)::date,
                            CURRENT_DATE,
                            '1 day'::interval
                          ) d
                LEFT JOIN planning_slot S
                    ON d::date >= S.start_datetime::date
                    AND d::date <= S.end_datetime::date
                LEFT JOIN hr_employee E ON E.id = S.employee_id
                LEFT JOIN (
                    SELECT DISTINCT ON (employee_id) *
                    FROM hr_version
                    ORDER BY employee_id, date_version DESC
                ) V ON V.employee_id = E.id
               ) AS t
         WHERE t.employee_id IS NOT NULL
           AND entry_date <= CURRENT_DATE
      GROUP BY t.entry_date, t.employee_id, t.department_id, t.company_id, t.hourly_cost
      ORDER BY t.entry_date, t.employee_id
        """

        drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            SQL(
                """CREATE OR REPLACE VIEW %s AS (%s)""",
                SQL.identifier(self._table),
                SQL(query),
            )
        )

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        if not order and groupby:
            order = ', '.join(f"{spec} DESC" if spec.startswith('date:') else spec for spec in groupby)
        return super().formatted_read_group(domain, groupby, aggregates, having=having, offset=offset, limit=limit, order=order)
