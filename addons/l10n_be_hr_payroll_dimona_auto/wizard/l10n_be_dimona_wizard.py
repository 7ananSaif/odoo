# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class L10nBeDimonaWizard(models.TransientModel):
    _inherit = 'l10n.be.dimona.wizard'

    def submit_declaration(self):
        self.ensure_one()
        if not self.version_id:
            raise UserError(_('There is no contract defined on the employee form.'))
        if self.declaration_type == 'in':
            if self.version_id.l10n_be_dimona_declaration_id and self.version_id.l10n_be_dimona_declaration_id.state != 'B':
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
