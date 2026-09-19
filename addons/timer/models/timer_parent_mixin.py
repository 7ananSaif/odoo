# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import MissingError


class TimerParentMixin(models.AbstractModel):
    _name = 'timer.parent.mixin'
    _description = 'Parent Timer Mixin'
    _inherit = 'timer.mixin'

    def _search_is_timer_running(self, operator, value):
        if operator not in ['=', '!='] or not isinstance(value, bool):
            raise NotImplementedError(_('Operation not supported'))

        running_timer = self.env['timer.timer'].search([
            ('timer_start', '!=', False),
            ('timer_pause', '=', False),
            ('parent_res_model', '=', self._name),
        ])

        if operator == '!=':
            value = not value

        return [('id', 'in' if value else 'not in', running_timer.mapped('parent_res_id'))]

    def _search_user_timer_id(self, operator, value):
        timers = self.env['timer.timer'].search([
            ('id', operator, value),
            ('user_id', '=', self.env.user.id),
        ])
        return [('id', 'in', timers.mapped('parent_res_id'))]

    @api.depends_context('uid')
    def _compute_user_timer_id(self):
        """ Get the timers according these conditions
            :user_id is is the current user
            :res_id is the current record
            :res_model is the current model
        """
        timer_read_group = self.env['timer.timer']._read_group(
            [
                ('user_id', '=', self.env.user.id),
                ('parent_res_id', 'in', self.ids),
                ('parent_res_model', '=', self._name),
            ],
            ['parent_res_id'],
            ['id:recordset'],
        )
        timer_by_model = {parent_res_id: timers[:1] for parent_res_id, timers in timer_read_group}
        for record in self:
            record.user_timer_id = timer_by_model.get(record.id, False)

    def action_timer_stop(self):
        """ Stop the timer of the current record
            Unlink the timer, it's useless to keep the stopped timer.
            A new timer can be create if needed
            Return the amount of minutes spent
        """
        self.ensure_one()
        record = self._get_record_with_timer_running()
        if record:
            return record.action_timer_stop()
        return super().action_timer_stop()

    def _create_record_to_start_timer(self):
        """ Create record to start a timer on this record. """
        return False

    def _get_timer_vals(self):
        return {
            'parent_res_id': self.id,
            'parent_res_model': self._name,
        }

    def _create_timer(self, vals=None):
        record = self._create_record_to_start_timer()
        if not record:
            raise MissingError(self.env._('Impossible to start a timer if no record exists to link it to.'))
        return record._create_timer(self._get_timer_vals())

    def _get_record_with_timer_running(self):
        if self.user_timer_id:
            return self.user_timer_id._get_related_document()
        return False

    @api.model
    def _get_user_timers(self):
        # Return user's timers. Can have multiple timers if some are in pause
        return self.env['timer.timer']._get_timers()

    def _get_timers_from_other_users(self):
        return self.env['timer.timer'].search([
            ('parent_res_model', '=', self._name),
            ('parent_res_id', 'in', self.ids),
            ('user_id', '!=', self.env.user.id),
        ])
