from odoo import fields, models, api


class PosPrepStage(models.Model):
    _name = 'pos.prep.stage'
    _description = 'Pos Preparation Stage'
    _inherit = ['pos.load.mixin']
    _order = 'sequence, id'

    name = fields.Char("Name", required=True)
    color = fields.Char("Color")
    alert_timer = fields.Integer(string="Alert timer (min)", help="Timer after which the order will be highlighted")
    prep_display_id = fields.Many2one('pos.prep.display', string="Preparation display", ondelete='cascade', index='btree_not_null')
    sequence = fields.Integer("Sequence")

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        stage_ids = data['pos.prep.display'][0]['stage_ids']
        return [('id', 'in', stage_ids)]

    def is_stage_position(self, position):
        stage_ids = self.prep_display_id.stage_ids
        return len(stage_ids) >= abs(position) and self.id == stage_ids[position].id
