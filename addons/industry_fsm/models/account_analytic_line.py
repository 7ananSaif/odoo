# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools import get_lang

class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def action_timer_start(self):
        res = super().action_timer_start()
        if self.task_id.is_fsm and self.timer_start:
            time = fields.Datetime.context_timestamp(self, self.timer_start)
            self.task_id.message_post(
                body=self.env._(
                    'Timer started at: %(date)s %(time)s',
                    date=time.strftime(get_lang(self.env).date_format),
                    time=time.strftime(get_lang(self.env).time_format),
                ),
            )
        return res

    def action_timer_stop(self, try_to_match=False):
        fsm_task = self.env['project.task']
        if self.task_id.is_fsm and self.timer_start:
            fsm_task = self.task_id
        minutes_spent = super().action_timer_stop(try_to_match)
        if fsm_task:
            time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            fsm_task.message_post(
                body=self.env._(
                    "Timer stopped at: %(date)s %(time)s",
                    date=time.strftime(get_lang(self.env).date_format),
                    time=time.strftime(get_lang(self.env).time_format),
                )
            )
        return minutes_spent
