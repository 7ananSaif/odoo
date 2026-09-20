# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _



class TimerMixin(models.AbstractModel):
    _name = 'timer.mixin'
    _description = 'Timer Mixin'

    timer_start = fields.Datetime(related='user_timer_id.timer_start', export_string_translation=False)
    timer_pause = fields.Datetime(related='user_timer_id.timer_pause', export_string_translation=False)
    is_timer_running = fields.Boolean(related='user_timer_id.is_timer_running', search="_search_is_timer_running", export_string_translation=False)
    user_timer_id = fields.One2many('timer.timer', compute='_compute_user_timer_id', search='_search_user_timer_id', export_string_translation=False)

    def _search_is_timer_running(self, operator, value):
        if operator != 'in':
            return NotImplemented

        running_timer_query = self.env['timer.timer']._search([
            ('timer_start', '!=', False),
            ('timer_pause', '=', False),
            ('res_model', '=', self._name),
        ])

        return [('id', 'in', running_timer_query.subselect('res_id'))]

    def _search_user_timer_id(self, operator, value):
        timer_query = self.env['timer.timer']._search([
            ('id', operator, value),
            ('user_id', '=', self.env.user.id),
            ('res_model', '=', self._name),
        ])
        return [('id', 'in', timer_query.subselect('res_id'))]

    @api.depends_context('uid')
    def _compute_user_timer_id(self):
        """ Get the timers according these conditions
            :user_id is is the current user
            :res_id is the current record
            :res_model is the current model
            limit=1 by security but the search should never have more than one record
        """
        timer_read_group = self.env['timer.timer']._read_group(
            domain=[
                ('user_id', '=', self.env.user.id),
                ('res_id', 'in', self.ids),
                ('res_model', '=', self._name),
            ],
            groupby=['res_id'],
            aggregates=['id:array_agg'])
        timer_by_model = dict(timer_read_group)
        for record in self:
            record.user_timer_id = timer_by_model.get(record.id, False)

    @api.model
    def _get_user_timers(self):
        # Return user's timers. Can have multiple timers if some are in pause
        return self.env['timer.timer'].search([('user_id', '=', self.env.user.id)])

    def unlink(self):
        if not self:
            return True
        timers = self._get_timers_from_other_users()
        if timers:
            self.check_access('unlink')
            timers.sudo().unlink()
        return super().unlink()

    def _get_timer_vals(self):
        return {
            'timer_start': False,
            'timer_pause': False,
            'is_timer_running': False,
            'res_model': self._name,
            'res_id': self.id,
            'user_id': self.env.user.id,
        }

    def _create_timer(self, vals=None):
        if not vals:
            vals = {}
        return self.env['timer.timer'].create({
            **self._get_timer_vals(),
            **vals,
        })

    def action_timer_start(self):
        """ Start the timer of the current record
        First, if a timer is running, stop or pause it
        If there isn't a timer for the current record, create one then start it
        Otherwise, resume or start it
        """
        self.ensure_one()
        self.sudo()._stop_timer_in_progress()
        timer = self.user_timer_id
        if not timer:
            timer = self._create_timer()
            timer.action_timer_start()
        else:
            # Check if it is in pause then resume it or start it
            if timer.timer_pause:
                timer.action_timer_resume()
            else:
                timer.action_timer_start()

    def action_timer_stop(self):
        """ Stop the timer of the current record
        Unlink the timer, it's useless to keep the stopped timer.
        A new timer can be create if needed
        Return the amount of minutes spent
        """
        self.ensure_one()
        timer = self.user_timer_id
        minutes_spent = timer.action_timer_stop()
        timer.unlink()
        return minutes_spent

    def action_timer_pause(self):
        self.ensure_one()
        timer = self.user_timer_id
        timer.action_timer_pause()

    def action_timer_resume(self):
        self.ensure_one()
        self._stop_timer_in_progress()
        timer = self.user_timer_id
        timer.action_timer_resume()

    def _get_timers_from_other_users(self):
        return self.env['timer.timer'].search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
            ('user_id', '!=', self.env.user.id),
        ])

    def _action_interrupt_user_timers(self):
        # Interruption is the action called when the timer is stoped by the start of another one
        self.action_timer_pause()

    def _stop_timer_in_progress(self):
        """
        Cancel the timer in progress if there is one
        Each model can interrupt the running timer in a specific way
        By setting it in pause or stop by example
        """
        timers = self._get_user_timers().filtered(lambda t: t.is_timer_running)
        for timer in timers:
            model = self.env[timer.res_model].browse(timer.res_id)
            model._action_interrupt_user_timers()
