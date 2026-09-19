# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models, fields
from odoo.exceptions import ValidationError

from dateutil.relativedelta import relativedelta


class L10nChHrEmployeeChildren(models.Model):
    _name = 'l10n.ch.hr.employee.children'
    _description = 'Employee Children'

    employee_id = fields.Many2one('hr.employee')
    name = fields.Char("Complete Name", required=True)
    last_name = fields.Char("Last Name")
    sex = fields.Selection(selection=[('M', 'Male'), ('F', 'Female')])
    birthdate = fields.Date()
    l10n_ch_sv_as_number = fields.Char("SV-AS Number")

    deduction_start = fields.Date(
        required=False, compute='_compute_deduction_start', store=True, readonly=False,
        help="Beginning of the right to the child deduction")
    deduction_end = fields.Date()

    @api.depends('birthdate')
    def _compute_deduction_start(self):
        for child in self:
            if not child.birthdate or child.deduction_start:
                continue
            child.deduction_start = child.birthdate.replace(day=1) + relativedelta(months=1)

    @api.constrains('deduction_end')
    def _check_deduction_end(self):
        for child in self:
            if child.deduction_end and child.deduction_end < child.deduction_start:
                raise ValidationError(_('End of deduction period cannot be before the starting period'))

    @api.constrains('l10n_ch_sv_as_number')
    def _check_l10n_ch_sv_as_number(self):
        """
        SV-AS number is encoded using EAN13 Standard Checksum control
        """
        for child in self:
            if not child.l10n_ch_sv_as_number:
                continue
            self.env['hr.employee']._validate_sv_as_number(child.l10n_ch_sv_as_number)
