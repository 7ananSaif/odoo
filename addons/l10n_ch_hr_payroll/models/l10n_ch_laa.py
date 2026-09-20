# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import re
import string

uid_bfs_pattern = r'CHE-[0-9]{3}\.[0-9]{3}\.[0-9]{3}'


class L10nChAccidentInsurance(models.Model):
    # YTI TODO Rename into l10n.ch.laa.insurance
    _name = 'l10n.ch.accident.insurance'
    _description = 'Swiss: Accident Insurances (AAP/AANP)'

    @api.model
    def _get_default_laa_group_ids(self):
        vals = [
            (0, 0, {
                'name': "LAA Group A",
                'group_unit': "A",
            })
        ]
        return vals

    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    name = fields.Char(required=True)
    customer_number = fields.Char(required=True)
    contract_number = fields.Char(required=True)
    # https://www.swissdec.ch/fileadmin/user_upload/_Datenempfaenger/Empfaengerliste.pdf
    insurance_code = fields.Char(required=True)
    line_ids = fields.One2many('l10n.ch.accident.insurance.line', 'insurance_id')
    uid_bfs_number = fields.Char(required=False)
    laa_group_ids = fields.One2many('l10n.ch.accident.group', 'insurance_id', default=_get_default_laa_group_ids)

    @api.constrains('uid_bfs_number')
    def _check_uid_bfs_number(self):
        """
        Identification Number (UID-BFS) must be either empty or have the right format and respect
        the modulo 11 checksum.
        """
        for record in self:
            if record.uid_bfs_number:
                if re.fullmatch(uid_bfs_pattern, record.uid_bfs_number):
                    if not self.env['res.company']._l10n_ch_modulo_11_checksum(record.uid_bfs_number, 8):
                        raise ValidationError(_("Identification Number (IDE-OFS) checksum is not correct"))
                else:
                    raise ValidationError(_("Identification Number (IDE-OFS) does not match the right format"))


class l10nChAccidentInsuranceGroup(models.Model):
    _name = "l10n.ch.accident.group"
    _description = "LAA Group category"

    @api.model
    def _get_default_laa_line_ids(self):
        vals = [
            (0, 0, {
                'date_from': fields.Date.today().replace(month=1, day=1),
                'threshold': 148200,
                'occupational_male_rate': 0,
                'non_occupational_male_rate': 0,
                'employer_aanp_part': '0',
            })
        ]
        return vals

    name = fields.Char()
    group_unit = fields.Selection(selection=[(char, char) for char in string.ascii_uppercase[string.ascii_uppercase.index('A'):]], required=True, string="Group Unit")
    insurance_id = fields.Many2one('l10n.ch.accident.insurance')
    line_ids = fields.One2many('l10n.ch.accident.insurance.line.rate', 'group_id', default=_get_default_laa_line_ids)

    def get_rates(self, target):
        self.ensure_one()
        for line in self.line_ids:
            if line.date_from <= target and (not line.date_to or target <= line.date_to):
                return line.threshold, line.occupational_male_rate, line.non_occupational_male_rate, int(line.employer_aanp_part or 0)
        raise UserError(_('No AAP/AANP threshold found for date %s', target))


class L10nChAccidentInsuranceLine(models.Model):
    _name = 'l10n.ch.accident.insurance.line'
    _description = 'Swiss: Accident Insurances Line (AAP/AANP)'
    _rec_name = 'solution_name'

    insurance_id = fields.Many2one('l10n.ch.accident.insurance')
    solution_name = fields.Char()
    solution_type = fields.Selection(selection=[
        ('A', 'A'),
        ('B', 'B')], required=True)
    solution_number = fields.Selection(selection=[
        ('0', '0 - Not insured (e.g. member of the board of directors not working in the company)'),
        ('1', '1 - Occupational and Non-Occupational Insured, with deductions'),
        ('2', '2 - Occupational and Non-Occupational Insured, without deductions'),
        ('3', '3 - Only Occupational Insured, without deductions (< 8 weekly hours)')], required=True, help="""
0: Not UVG insured (e.g. member of the board of directors not working in the company)
1: AAP and AANP insured, with AANP deduction
2: Insured AAP and AANP, without AANP deduction
3: Only AAP insured, so no AANP deduction (for employees whose weekly work is < 8 h))""")
    rate_ids = fields.One2many('l10n.ch.accident.insurance.line.rate', 'line_id')
    solution_code = fields.Char(compute='_compute_solution_code', store=True)

    @api.depends('solution_type', 'solution_number')
    def _compute_solution_code(self):
        for line in self:
            line.solution_code = line.solution_type + line.solution_number

    def _get_threshold(self, target):
        if not self:
            return 0
        for line in self.rate_ids:
            if line.date_from <= target and (not line.date_to or target <= line.date_to):
                return line.threshold
        raise UserError(_('No AAP/AANP threshold found for date %s', target))

    def _get_occupational_rates(self, target, gender="male"):
        if not self:
            return 0, 0
        for line in self.rate_ids:
            if line.date_from <= target and (not line.date_to or target <= line.date_to):
                if gender == "male":
                    return line.occupational_male_rate, int(line.employer_occupational_part)
                if gender == "female":
                    return line.occupational_female_rate, int(line.employer_occupational_part)
                raise UserError(_('No found rate for gender %s', gender))
        raise UserError(_('No AAP rates found for date %s', target))

    def _get_non_occupational_rates(self, target, gender="male"):
        if not self:
            return 0, 0
        for line in self.rate_ids:
            if line.date_from <= target and (not line.date_to or target <= line.date_to):
                if gender == "male":
                    return line.non_occupational_male_rate, int(line.employer_non_occupational_part)
                if gender == "female":
                    return line.non_occupational_female_rate, int(line.employer_non_occupational_part)
                raise UserError(_('No found rate for gender %s', gender))
        raise UserError(_('No AANP rates found for date %s', target))


class L10nChAccidentInsuranceLineRate(models.Model):
    _name = 'l10n.ch.accident.insurance.line.rate'
    _description = 'Swiss: Accident Insurances Line Rate (AAP/AANP)'

    group_id = fields.Many2one('l10n.ch.accident.group')
    line_id = fields.Many2one('l10n.ch.accident.insurance.line')
    date_from = fields.Date(string="From", required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(string="To")
    threshold = fields.Float(default=148200)
    occupational_male_rate = fields.Float("Occupational Male Rate (%)", digits='Payroll Rate')
    occupational_female_rate = fields.Float("Occupational Female Rate (%)", digits='Payroll Rate')
    non_occupational_male_rate = fields.Float("Non-occupational Male Rate (%)", digits='Payroll Rate')
    non_occupational_female_rate = fields.Float("Non-occupational Female Rate (%)", digits='Payroll Rate')
    employer_occupational_part = fields.Selection([
        ('0', '0 %'),
        ('50', '50 %'),
        ('100', '100 %'),
    ], string="Company Occupational Part", default='50')
    employer_non_occupational_part = fields.Selection([
        ('0', '0 %'),
        ('50', '50 %'),
        ('100', '100 %'),
    ], string="Company Non Occupational Part", default='50')
    employer_aanp_part = fields.Selection(selection=[('0', "0 %"),
                                                     ('50', "50 %")], default="0")
