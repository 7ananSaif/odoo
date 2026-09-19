# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    # speeds up `l10n_be.work.entry.daily.benefit.report`
    _daily_benefit_idx = models.Index("(active, employee_id) WHERE state IN ('draft', 'validated')")

    def _get_leaves_entries_outside_schedule(self):
        return super()._get_leaves_entries_outside_schedule().filtered(lambda w: not w.work_entry_type_id.l10n_be_is_time_credit)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        partial_sick_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_part_sick')
        leaves = self.env['hr.leave']
        for work_entry in res:
            if work_entry.work_entry_type_id == partial_sick_work_entry_type and work_entry.leave_id:
                leaves |= work_entry.leave_id
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        res_model_id = self.env.ref('hr_holidays.model_hr_leave').id
        activity_vals = []
        for leave in leaves.sudo():
            user_ids = leave.holiday_status_id.responsible_ids.ids or self.env.user.ids
            note = _("Sick time off to report to DRS for %s.", leave.date_from.strftime('%B %Y'))
            for user_id in user_ids:
                activity_vals.append({
                    'activity_type_id': activity_type_id,
                    'automated': True,
                    'note': note,
                    'user_id': user_id,
                    'res_id': leave.id,
                    'res_model_id': res_model_id,
                })
        # TDE TODO: batch schedule with record-based note
        self.env['mail.activity'].create(activity_vals)
        return res
