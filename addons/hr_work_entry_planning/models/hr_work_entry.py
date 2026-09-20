# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    planning_slot_id = fields.Many2one('planning.slot', groups='hr.group_hr_user', index='btree_not_null')
