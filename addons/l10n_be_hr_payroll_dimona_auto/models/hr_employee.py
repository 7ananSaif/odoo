# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_be_dimona_declaration_id = fields.Many2one(readonly=False, related="version_id.l10n_be_dimona_declaration_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_last_dimona_declaration_id = fields.Many2one(readonly=False, related="version_id.l10n_be_last_dimona_declaration_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_in = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_in", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_update = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_update", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_out = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_out", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_needs_dimona_cancel = fields.Boolean(readonly=False, related="version_id.l10n_be_needs_dimona_cancel", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_next_action = fields.Selection(readonly=True, related="version_id.l10n_be_dimona_next_action", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_be_dimona_relation_id = fields.Many2one('l10n.be.dimona.relation', string='Dimona Relation', groups="hr_payroll.group_hr_payroll_user")

    def action_open_dimona(self):
        for employee in self:
            if not employee.l10n_be_needs_dimona_in:
                continue
            employee.version_id.action_open_dimona()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_update_dimona(self):
        for employee in self:
            if not employee.l10n_be_needs_dimona_update:
                continue
            employee.version_id.action_update_dimona()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_close_dimona(self):
        for employee in self:
            if not employee.l10n_be_needs_dimona_out:
                continue
            employee.version_id.action_close_dimona()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_cancel_dimona(self):
        for employee in self:
            if not employee.l10n_be_needs_dimona_cancel:
                continue
            employee.version_id.action_cancel_dimona()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            for employee in self:
                # As this is impossible to archive a version if it's the only employee version
                # could be required to cancel a dimona if there was no date_end on the dimona
                # IN and we archive the employee itself.
                if employee.active and len(employee.version_ids) == 1 and employee.version_ids.l10n_be_dimona_declaration_id and not employee.version_ids.l10n_be_dimona_declaration_id.date_end:
                    employee.version_ids.l10n_be_needs_dimona_cancel = True
        return super().write(vals)

    def action_open_relation(self):
        self.ensure_one()
        return {
            'name': _('Dimona Relation'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_id': self.l10n_be_dimona_relation_id.id,
            'res_model': 'l10n.be.dimona.relation',
        }
