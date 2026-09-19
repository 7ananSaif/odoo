# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from odoo import api, models, _
from odoo.exceptions import UserError


def batch(iterable, batch_size):
    l = len(iterable)
    for n in range(0, l, batch_size):
        yield iterable[n:min(n + batch_size, l)]


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _create_work_entries(self):
        # Similar to `_create_work_entries` for attendances but this function assumes big batches
        # (due to the publish button that published all slots)
        # Also note that slots are assumed to stay as is after being published, any other change will need a
        # full work entry regeneration.
        self_with_employee = self.filtered(lambda s: s.employee_id)
        if not self_with_employee:
            return
        # The procedure for creating a work entry within an already generated period
        # is more complicated for planning slots than for leaves because leaves override
        # attendance periods, here we are not able to just archive work entries we do not want
        # etc...
        # We will instead archive all work entries that are touched by the current planning slot's period
        # (slots don't have an overlap constraint), and regenerate all work entries that were covered by them.
        # Since all we need is already in the database we can use that query to have better performance.
        self.flush_model(['start_datetime', 'end_datetime', 'employee_id'])
        self.env['hr.version'].flush_model([
            'employee_id', 'work_entry_source',
            'contract_date_start', 'contract_date_end', 'date_generated_from', 'date_generated_to'
        ])
        self.env['hr.work.entry'].flush_model(['employee_id', 'date'])
        self.env.cr.execute("""
            SELECT slot.id as id,
                   ARRAY_AGG(DISTINCT version.id) as version_ids,
                   ARRAY_AGG(DISTINCT hwe.id) as work_entry_ids,
                   slot.start_datetime as start,
                   slot.end_datetime as stop
              FROM planning_slot slot
              JOIN hr_employee employee
                ON slot.employee_id = employee.id AND
                   employee.active
        -- Keeping only the last version.
        -- We consider that work entries that covers two versions should not be handled as super rare.
        INNER JOIN (SELECT DISTINCT ON (employee_id) *
                                  FROM hr_version v
                              ORDER BY employee_id, date_version DESC) version
                ON version.employee_id = employee.id AND
                   version.work_entry_source = 'planning' AND
                   version.date_generated_from < slot.end_datetime AND
                   version.date_generated_to > slot.start_datetime AND
                   version.contract_date_start <= slot.end_datetime AND
                   (version.contract_date_end IS NULL OR
                    version.contract_date_end >= slot.start_datetime)
         LEFT JOIN hr_work_entry hwe
                ON hwe.employee_id = slot.employee_id AND
                   hwe.date <= slot.end_datetime::date AND
                   hwe.date >= slot.start_datetime::date
             WHERE slot.id in %s
          GROUP BY slot.id
        """, [tuple(self_with_employee.ids)])
        query_result = self.env.cr.dictfetchall()
        # Group by period to generate to profit from batching
        # Contains [(start, stop)] = [version_ids]
        periods_to_generate = defaultdict(list)
        work_entries_to_archive = []
        for row in query_result:
            periods_to_generate[row['start'], row['stop']].extend(row['version_ids'])
            if any(row['work_entry_ids']):
                work_entries_to_archive.extend(row['work_entry_ids'])
        self.env['hr.work.entry'].sudo().browse(work_entries_to_archive).write({'active': False})
        work_entries_vals_list = []
        for period, version_ids in periods_to_generate.items():
            if not version_ids:
                continue
            contracts = self.env['hr.version'].sudo().browse(version_ids)
            work_entries_vals_list.extend(contracts._get_work_entries_values(period[0], period[1]))
        work_entries_vals_list = self.env['hr.version']._generate_work_entries_postprocess(work_entries_vals_list)
        self.env['hr.work.entry'].sudo().create(work_entries_vals_list)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.filtered(lambda s: s.state == 'published')._create_work_entries()
        return res

    def write(self, vals):
        if vals.get('resource_id') or vals.get('start_datetime') or vals.get('end_datetime') or vals.get('allocated_hours'):
            validated_work_entries = self.env['hr.work.entry'].sudo().search([('planning_slot_id', 'in', self.ids), ('state', '=', 'validated')])
            if validated_work_entries:
                raise UserError(_("This shift record is linked to a validated working entry. You can't modify it."))
        state = vals.get('state')
        concerned_slots = self.filtered(lambda s: s.state != state) if state\
            else self.env['planning.slot']
        res = super().write(vals)
        concerned_slots._create_work_entries()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_validated_work_entries(self):
        validated_work_entries = self.env['hr.work.entry'].sudo().search([('planning_slot_id', 'in', self.ids), ('state', '=', 'validated')])
        if validated_work_entries:
            raise UserError(_("This shift record is linked to a validated working entry. You can't delete it."))

    def unlink(self):
        # Archive linked work entries upon deleting slots
        self.env['hr.work.entry'].sudo().search([('planning_slot_id', 'in', self.ids)]).write({'active': False})
        return super().unlink()

    def _get_planning_duration(self, date_start, date_stop):
        '''
        If the interval(date_start, date_stop) is equal to the planning_slot's interval, return the slot's allocated hours.
        If the interval(date_start, date_stop) is a subset of the planning_slot's interval,
        a new (non saved) planning_slot will be created to compute the duration according to planning rules.
        If the interval(date_start, date_stop) is not fully inside of the planning_slot's interval the behaviour is undefined

        :return: The real duration according to the planning app
        :rtype: number
        '''
        self.ensure_one()
        if self.start_datetime == date_start and self.end_datetime == date_stop:
            return self.allocated_hours
        new_slot = self.env['planning.slot'].new({
            **self.read(['employee_id', 'company_id', 'allocated_percentage', 'resource_id'])[0],
            'start_datetime': date_start,
            'end_datetime': date_stop,
        })
        return new_slot.allocated_hours
