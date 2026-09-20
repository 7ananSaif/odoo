# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.sql import drop_view_if_exists, SQL


class L10n_BeWorkEntryDailyBenefitReport(models.Model):
    """Generates a list of combination of dates, benefit name and employee_id.
       The list is created in accordance with:
       * The work entries currently in the system and the benefits associated with the work entry types.
       * The assumption that a work entry, even minimal (at least 1 hour) is enough to grant the benefit for
         that day.
    """
    _name = 'l10n_be.work.entry.daily.benefit.report'
    _description = 'Work Entry Related Benefit Report'
    _auto = False

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    day = fields.Date(readonly=True)
    benefit_name = fields.Char('Benefit Name', readonly=True)

    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        statement = SQL("""
            CREATE OR REPLACE VIEW %s AS (
                    SELECT work_entry.employee_id,
                           work_entry.date AS day,
                           advantage.benefit_name,
                           1 AS id

                      FROM hr_work_entry work_entry
                      JOIN hr_version version ON work_entry.version_id = version.id
                       AND work_entry.active
                       AND work_entry.state::TEXT = ANY (ARRAY ['draft', 'validated'])
                      JOIN resource_calendar calendar ON version.resource_calendar_id = calendar.id
                      JOIN hr_work_entry_type ON work_entry.work_entry_type_id = hr_work_entry_type.id
                       AND (
                            hr_work_entry_type.meal_voucher = TRUE OR
                            hr_work_entry_type.private_car = TRUE OR
                            hr_work_entry_type.representation_fees = TRUE
                       )
                CROSS JOIN LATERAL (
                            VALUES
                                ('meal_voucher'::text,hr_work_entry_type.meal_voucher),
                                ('private_car'::text,hr_work_entry_type.private_car),
                                ('representation_fees'::text,hr_work_entry_type.representation_fees)
                        ) AS advantage(benefit_name, is_applicable)
                     WHERE advantage.is_applicable
                  GROUP BY 1,2,3
            );
        """, SQL.identifier(self._table))
        self.env.cr.execute(statement)
