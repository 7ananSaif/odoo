# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo import api, fields, models, _


class L10nBeDimonaRelation(models.Model):
    _name = 'l10n.be.dimona.relation'
    _description = 'Dimona Relation'

    name = fields.Char('NISS', required=True, readonly=True, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    period_ids = fields.One2many('l10n.be.dimona.period', 'relation_id')
    content = fields.Json()
    employee_id = fields.Many2one('hr.employee', compute='_compute_relation_info', store=True, readonly=True)
    date_start = fields.Date(compute='_compute_relation_info', store=True, readonly=True)
    date_end = fields.Date(compute='_compute_relation_info', store=True, readonly=True)
    period_count = fields.Integer(compute='_compute_period_count')

    _constraint_name_unique = models.Constraint(
        definition='unique(name)',
        message="The dimona relation ID must be unique!",
    )

    @api.depends('content')
    def _compute_relation_info(self):
        for relation in self:
            if 'startDate' in relation.content:
                (year, month, day) = relation.content['startDate'].split('-')
                relation.date_start = date(int(year), int(month), int(day))

            if 'endDate' in relation.content:
                (year, month, day) = relation.content['endDate'].split('-')
                relation.date_end = date(int(year), int(month), int(day))

            relation.employee_id = self.env['hr.employee'].with_context(active_test=False).search([
                ('niss', '=', relation.name)
            ], order="active DESC", limit=1)
            if relation.employee_id:
                relation.employee_id.l10n_be_dimona_relation_id = relation

    @api.depends('period_ids')
    def _compute_period_count(self):
        for relation in self:
            relation.period_count = len(relation.period_ids)

    def action_open_periods(self):
        if self.period_count == 1:
            return {
                'name': _('Dimona Period'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_id': self.period_ids.id,
                'res_model': 'l10n.be.dimona.period',
            }
        return {
            'name': _('Dimona Periods'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.be.dimona.period',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.period_ids.ids)],
        }
