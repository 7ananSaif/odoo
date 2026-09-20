# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo import api, fields, models, _


class L10nBeDimonaPeriod(models.Model):
    _name = 'l10n.be.dimona.period'
    _description = 'Dimona Period'
    _order = 'date_start ASC'

    name = fields.Char('Period ID', required=True, readonly=True, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    relation_id = fields.Many2one('l10n.be.dimona.relation', 'relation_id', compute='_compute_period_info', store=True, readonly=True)
    declaration_ids = fields.One2many('l10n.be.dimona.declaration', 'period_id')
    employee_id = fields.Many2one('hr.employee', compute='_compute_period_info', store=True, readonly=True)
    date_start = fields.Date(compute='_compute_period_info', store=True, readonly=True)
    date_end = fields.Date(compute='_compute_period_info', store=True, readonly=True)
    content = fields.Json()
    declaration_count = fields.Integer(compute='_compute_declaration_count')

    _constraint_name_unique = models.Constraint(
        definition='unique(name)',
        message="The dimona period ID must be unique!",
    )

    @api.depends('content')
    def _compute_period_info(self):
        for period in self:
            if 'startDate' in period.content:
                (year, month, day) = period.content['startDate'].split('-')
                period.date_start = date(int(year), int(month), int(day))

            if 'endDate' in period.content:
                (year, month, day) = period.content['endDate'].split('-')
                period.date_end = date(int(year), int(month), int(day))

            period.employee_id = self.env['hr.employee'].with_context(active_test=False).search([
                ('niss', '=', period.content['worker']['ssin'])
            ], order="active DESC", limit=1)

            period.relation_id = self.env['l10n.be.dimona.relation'].search([
                ('name', '=', period.content['worker']['ssin'])
            ])

    @api.depends('declaration_ids')
    def _compute_declaration_count(self):
        for relation in self:
            relation.declaration_count = len(relation.declaration_ids)

    def action_open_declarations(self):
        if self.declaration_count == 1:
            return {
                'name': _('Dimona Declaration'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_id': self.declaration_ids.id,
                'res_model': 'l10n.be.dimona.declaration',
            }
        return {
            'name': _('Dimona Declarations'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.be.dimona.declaration',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.declaration_ids.ids)],
        }
