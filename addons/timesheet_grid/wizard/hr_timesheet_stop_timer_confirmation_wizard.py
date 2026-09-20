# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrTimesheetStopTimerConfirmationWizard(models.Model):
    _name = 'hr.timesheet.stop.timer.confirmation.wizard'
    _description = 'Confirm timesheet creation when stop timer'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        timesheet = self.env['account.analytic.line'].browse(self.env.context.get('default_timesheet_id', False))
        if timesheet:
            res['timesheet_name'] = timesheet.name if timesheet.name != "/" else ""
            if timesheet.user_timer_id:
                minutes_spent = timesheet.user_timer_id._get_minutes_spent()
                res['time_spent'] = timesheet.get_rounded_time(minutes_spent) + timesheet.unit_amount
        return res

    timesheet_id = fields.Many2one('account.analytic.line', string='Timesheet')
    timesheet_name = fields.Char('Name')
    time_spent = fields.Float('Time Spent')

    def action_delete_timesheet(self):
        self.timesheet_id.action_timer_unlink()

    def action_save_timesheet(self):
        self.timesheet_id.write({
            'name': self.timesheet_name,
            'unit_amount': self.time_spent,
        })
        self.timesheet_id.action_timer_unlink()
