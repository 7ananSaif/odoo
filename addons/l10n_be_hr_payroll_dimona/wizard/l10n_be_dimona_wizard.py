# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nBeDimonaWizard(models.TransientModel):
    _name = 'l10n.be.dimona.wizard'
    _description = 'Dimona Wizard'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(_('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    version_id = fields.Many2one(
        'hr.version', string='Employee Record', compute='_compute_version_id', store=True, readonly=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', default=lambda self: self.env.context.get('active_id'))
    employee_birthday = fields.Date(related='employee_id.birthday')
    contract_date_start = fields.Date(related='version_id.contract_date_start')
    contract_date_end = fields.Date(related='version_id.contract_date_end')
    contract_is_student = fields.Boolean(related='version_id.l10n_be_is_student')
    contract_wage_type = fields.Selection(related='version_id.wage_type')
    contract_country_code = fields.Char(related='version_id.country_code')
    contract_planned_hours = fields.Integer(related='version_id.l10n_be_dimona_planned_hours')
    without_niss = fields.Boolean(string="Employee Without NISS")

    declaration_type = fields.Selection(
        selection=[
            ('in', 'Register employee entrance'),
            ('out', 'Register employee departure'),
            ('update', 'Update employee information'),
            ('cancel', 'Cancel employee declaration')
        ], default='in')

    @api.depends('employee_id')
    def _compute_version_id(self):
        for wizard in self:
            wizard.version_id = wizard.employee_id.version_id

    def submit_declaration(self):
        self.ensure_one()
        if not self.version_id:
            raise UserError(_('There is no contract defined on the employee form.'))
        if self.declaration_type == 'in':
            if self.version_id.l10n_be_dimona_in_declaration_number:
                raise UserError(_('There is already a IN declaration for this contract.'))
            if self.version_id.l10n_be_is_student:
                if not self.version_id.l10n_be_dimona_planned_hours:
                    raise UserError(_('There is no defined planned hours on the student contract.'))
                if not self.version_id.date_end:
                    raise UserError(_('There is no defined end date on the student contract.'))
                if (self.version_id.date_end.month - 1) // 3 + 1 != (self.version_id.date_start.month - 1) // 3 + 1:
                    raise UserError(_('Start date and end date should belong to the same quarter.'))
                if self.version_id.date_start < fields.Date.today():
                    raise UserError(_('The DIMONA should be introduced before start date for students.'))
            self.version_id._action_open_dimona(foreigner=self.without_niss)
        elif self.declaration_type == 'out':
            if not self.contract_date_end:
                raise UserError(_('There is not end date defined on the employee contract.'))
            self.version_id._action_close_dimona()
        elif self.declaration_type == 'update':
            self.version_id._action_update_dimona()
        elif self.declaration_type == 'cancel':
            self.version_id._action_cancel_dimona()
        return {
            'name': self.employee_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'hr.version',
            'res_id': self.version_id.id,
            'views': [(False, 'form')]
        }
