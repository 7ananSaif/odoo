from odoo import fields, models, tools


class EsgEmployeeCommutingReport(models.Model):
    _name = 'esg.employee.commuting.report'
    _description = 'ESG Employee Commuting Report'
    _auto = False

    driver_id = fields.Many2one('res.partner', readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    date_from = fields.Date('Date', readonly=True)
    date_to = fields.Date(readonly=True)
    co2 = fields.Float('gCO₂/km', readonly=True)
    total_distance = fields.Float('km', readonly=True)
    total_co2 = fields.Float('tCO₂', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW esg_employee_commuting_report AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY log.vehicle_id, log.driver_id, month_start
                    ) AS id,
                    log.vehicle_id,
                    log.driver_id,
                    v.company_id,
                    rc.weekly_days_at_office,
                    month_start::DATE AS date_from,
                    (month_start + INTERVAL '1 month - 1 day')::DATE AS date_to,
                    v.co2,
                    SUM(
                        ve.distance_home_work * 2 * (
                            EXTRACT(DAY FROM (
                                LEAST(month_start + INTERVAL '1 month - 1 day', COALESCE(log.date_end, NOW() AT TIME ZONE 'utc'))
                                - GREATEST(month_start, log.date_start)
                            )) + 1
                        ) * v.co2 / 1e6
                    ) * rc.weekly_days_at_office / 7 AS total_co2,
                    SUM(
                        ve.distance_home_work * 2 * (
                            EXTRACT(DAY FROM (
                                LEAST(month_start + INTERVAL '1 month - 1 day', COALESCE(log.date_end, NOW() AT TIME ZONE 'utc'))
                                - GREATEST(month_start, log.date_start)
                            )) + 1
                        )
                    ) * rc.weekly_days_at_office / 7 AS total_distance
                FROM fleet_vehicle_assignation_log log
                JOIN fleet_vehicle v ON v.id = log.vehicle_id
                JOIN res_company rc ON rc.id = v.company_id
                JOIN hr_employee e ON e.work_contact_id = log.driver_id
                JOIN hr_version ve ON ve.id = e.current_version_id
                JOIN LATERAL (SELECT generate_series(
                    date_trunc('month', log.date_start),
                    date_trunc('month', COALESCE(log.date_end, NOW() AT TIME ZONE 'utc')),
                    '1 month'::INTERVAL
                )) g(month_start) ON TRUE
                GROUP BY
                    log.driver_id,
                    log.vehicle_id,
                    v.company_id,
                    month_start,
                    v.co2,
                    ve.distance_home_work,
                    rc.weekly_days_at_office
            )
        """)
