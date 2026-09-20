from odoo import fields, models
from odoo.addons.pos_enterprise.utils.date_utils import compute_seconds_since


class PosPreparationState(models.Model):
    _name = 'pos.prep.state'
    _description = 'Pos Preparation State'
    _inherit = ['pos.load.mixin']

    prep_line_id = fields.Many2one('pos.prep.line', string='Preparation Orderline', required=True, ondelete='cascade')
    todo = fields.Boolean("Status of the orderline", help="The status of a command line, todo or not", default=True)
    stage_id = fields.Many2one('pos.prep.stage', ondelete='cascade', index=True)
    last_stage_change = fields.Datetime(default=fields.Datetime.now)

    def change_state_status(self, todos, prep_display_id):
        pdis_state_todos = []

        for pdis_state in self:
            pdis_state.todo = todos[str(pdis_state.id)]
            pdis_state_todos.append({
                'id': pdis_state.id,
                'todo': pdis_state.todo
            })
            self._record_status_change_prep_time(pdis_state)

        p_dis = self.env['pos.prep.display'].browse(int(prep_display_id))
        p_dis._notify('CHANGE_STATE_STATUS', pdis_state_todos)

        return True

    def _record_status_change_prep_time(self, pdis_state):
        # If first stage & line is done, write the preparation_time
        if not pdis_state.todo and pdis_state.stage_id.is_stage_position(0) and pdis_state.prep_line_id.pos_order_line_id.preparation_time == -1:
            pdis_state.prep_line_id.pos_order_line_id.preparation_time = compute_seconds_since(pdis_state.last_stage_change)
        elif pdis_state.todo and pdis_state.stage_id.is_stage_position(0) and pdis_state.prep_line_id.pos_order_line_id.preparation_time != -1:
            pdis_state.prep_line_id.pos_order_line_id.preparation_time = -1
        # If second last stage & line is done, write the service_time
        if len(pdis_state.stage_id) > 1:
            if not pdis_state.todo and pdis_state.stage_id.is_stage_position(-2) and pdis_state.prep_line_id.pos_order_line_id.service_time == -1:
                pdis_state.prep_line_id.pos_order_line_id.service_time = compute_seconds_since(pdis_state.last_stage_change)
            elif pdis_state.todo and pdis_state.stage_id.is_stage_position(-2) and pdis_state.prep_line_id.pos_order_line_id.service_time != -1:
                pdis_state.prep_line_id.pos_order_line_id.service_time = -1

    def change_state_stage(self, stages, prep_display_id):
        pdis_state_stages = []
        prep_order_completion_time = {}

        for pdis_state in self:
            old_last_stage_change = pdis_state.last_stage_change
            pdis_state.todo = True
            pdis_state.stage_id = stages[str(pdis_state.id)]
            pdis_state.last_stage_change = pdis_state.write_date
            pdis_state_stages.append({
                'id': pdis_state.id,
                'stage_id': pdis_state.stage_id.id,
                'last_stage_change': pdis_state.last_stage_change
            })
            self._record_stage_change_prep_time(pdis_state, old_last_stage_change, prep_order_completion_time)

        p_dis = self.env['pos.prep.display'].browse(int(prep_display_id))
        p_dis._notify('CHANGE_STATE_STAGE', {'pdis_state_stages': pdis_state_stages, 'prep_order_completion_time': prep_order_completion_time})

        return True

    def _record_stage_change_prep_time(self, pdis_state, old_last_stage_change, prep_order_completion_time):
        # If new stage is the first one & line is not done, it means the order has been reset
        if pdis_state.stage_id.is_stage_position(0):
            if pdis_state.prep_line_id.pos_order_line_id.preparation_time != -1:
                pdis_state.prep_line_id.pos_order_line_id.preparation_time = -1
            if pdis_state.prep_line_id.pos_order_line_id.service_time != -1:
                pdis_state.prep_line_id.pos_order_line_id.service_time = -1
        # If new stage is the second last one & line is done, write the preparation_time
        if len(pdis_state.stage_id) > 1:
            if pdis_state.prep_line_id.pos_order_line_id.preparation_time == -1 and pdis_state.stage_id.is_stage_position(-2):
                pdis_state.prep_line_id.pos_order_line_id.preparation_time = compute_seconds_since(old_last_stage_change)
        # If new stage is the last one & line is done, write the service_time
        if pdis_state.prep_line_id.pos_order_line_id.service_time == -1 and pdis_state.stage_id.is_stage_position(-1):
            pdis_state.prep_line_id.pos_order_line_id.service_time = compute_seconds_since(old_last_stage_change)

        # If the order is done, write the completion_time
        # Also, if all the quantities are cancelled (don't have pos_order_line_id in that case), no need to update the completion_time
        if pdis_state.stage_id.is_stage_position(-1) and pdis_state.prep_line_id.prep_order_id.id not in prep_order_completion_time and pdis_state.prep_line_id.prep_order_id.prep_line_ids.pos_order_line_id:
            order_completion_seconds = max(
                pdis_state.prep_line_id.prep_order_id.prep_line_ids.pos_order_line_id.mapped(
                    lambda line: line.service_time + line.preparation_time
                )
            )
            order_completion_minutes = int(order_completion_seconds / 60)
            pdis_state.prep_line_id.prep_order_id.completion_time = order_completion_minutes
            prep_order_completion_time[pdis_state.prep_line_id.prep_order_id.id] = order_completion_minutes
