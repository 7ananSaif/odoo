# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import single_email_re

auto_mobile_re = re.compile(r"^\+\d{1,3}-\d{1,29}$")


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_hk_surname = fields.Char(
        string="Surname",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_given_name = fields.Char(
        string="Given Name",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_name_in_chinese = fields.Char(
        string="Name in Chinese",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_passport_place_of_issue = fields.Char(
        string="Place of Issue",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_identification_id = fields.Char(
        string="Spouse Identification No",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_passport_id = fields.Char(
        string="Spouse Passport No",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_spouse_passport_place_of_issue = fields.Char(
        string="Spouse Place of Issue",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_mpf_manulife_account = fields.Char(
        string="MPF Manulife Account",
        groups="hr_payroll.group_hr_payroll_user",
        tracking=True,
        copy=False,
    )
    l10n_hk_rental_ids = fields.One2many(
        comodel_name='l10n_hk.rental',
        inverse_name='employee_id',
        string='Rentals',
        copy=False,
        groups="hr.group_hr_user",
    )
    l10n_hk_rentals_count = fields.Integer(
        compute='_compute_l10n_hk_rentals_count',
        groups="hr.group_hr_user",
    )

    # Autopay fields
    l10n_hk_autopay_account_type = fields.Selection(
        selection=[
            ('bban', 'Bank Code + Account Number + Beneficiary Name'),
            ('svid', 'FPS ID'),
            ('emal', 'Email address + / Bank Code'),
            ('mobn', '(Country Code) Mobile Phone Number + / Bank Code'),
            ('hkid', 'HKID + Beneficiary Name'),
        ],
        default='bban',
        string='Autopay Payment Type',
        groups='hr.group_hr_user',
    )
    l10n_hk_autopay_svid = fields.Char(string='FPS Identifier', groups="hr.group_hr_user")
    l10n_hk_autopay_email = fields.Char(string='Autopay Email Address', groups="hr.group_hr_user")
    l10n_hk_autopay_mobile = fields.Char(string='Autopay Mobile Number', groups="hr.group_hr_user")
    l10n_hk_autopay_ref = fields.Char(string='Autopay Reference', groups="hr.group_hr_user")

    l10n_hk_internet = fields.Monetary(readonly=False, related="version_id.l10n_hk_internet", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_hk_mpf_vc_option = fields.Selection(readonly=False, related="version_id.l10n_hk_mpf_vc_option", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_hk_mpf_vc_percentage = fields.Float(readonly=False, related="version_id.l10n_hk_mpf_vc_percentage", inherited=True, groups="hr_payroll.group_hr_payroll_user")
    l10n_hk_rental_id = fields.Many2one(readonly=False, related="version_id.l10n_hk_rental_id", inherited=True, groups="hr_payroll.group_hr_payroll_user")

    @api.constrains('l10n_hk_autopay_email')
    def _check_l10n_hk_autopay_email(self):
        for employee in self:
            if employee.l10n_hk_autopay_email and not single_email_re.match(employee.l10n_hk_autopay_email):
                raise ValidationError(employee.env._('The "Autopay Email Address" field must be filled with a single correct email address.'))

    @api.constrains('l10n_hk_autopay_mobile')
    def _check_l10n_hk_auto_mobile(self):
        for employee in self:
            if employee.l10n_hk_autopay_mobile and not auto_mobile_re.match(employee.l10n_hk_autopay_mobile):
                raise ValidationError(employee.env._('The "Autopay Mobile Number" must match the format "+xxx-xxxxxxxx".'))

    @api.depends('l10n_hk_surname', 'l10n_hk_given_name')
    def _compute_legal_name(self):
        hk_employees = self.filtered(lambda e: e.company_id.country_code == 'HK' and (e.l10n_hk_surname or e.l10n_hk_given_name))
        for employee in hk_employees:
            employee.legal_name = ' '.join(filter(None, [employee.l10n_hk_surname, employee.l10n_hk_given_name]))

        super(HrEmployee, self - hk_employees)._compute_legal_name()

    @api.model
    def _get_years_of_service(self, period_start_date, period_end_date):
        """
        Calculates years of service according to the HK statutory methodology.

        This involves:
        1. Counting the number of full years of service.
        2. Prorating the remaining incomplete year by dividing the remaining days of service
           by the actual number of days in that specific annual cycle (365 or 366).
        :return: a float representing the number of years of service.
        """
        if period_start_date > period_end_date:
            return 0

        full_years = relativedelta(period_end_date, period_start_date).years
        last_anniversary_date = period_start_date + relativedelta(years=full_years)

        remaining_days = (period_end_date - last_anniversary_date).days + 1

        # The divisor is the total number of days in the 12-month cycle of the
        # incomplete year. For example, if the last anniversary was May 1, 2027,
        # this cycle is May 1, 2027, to April 30, 2028.
        next_anniversary_date = last_anniversary_date + relativedelta(years=1)
        days_in_pro_rata_year = (next_anniversary_date - last_anniversary_date).days

        return full_years + (remaining_days / days_in_pro_rata_year)

    @api.depends('l10n_hk_rental_ids')
    def _compute_l10n_hk_rentals_count(self):
        for employee in self:
            employee.l10n_hk_rentals_count = len(employee.l10n_hk_rental_ids)

    def action_open_rentals(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('l10n_hk_hr_payroll.action_l10n_hk_rental')
        action['views'] = [(False, 'list'), (False, 'form')]
        action['domain'] = [('id', 'in', self.l10n_hk_rental_ids.ids)]
        action['context'] = {'default_employee_id': self.id}
        return action
