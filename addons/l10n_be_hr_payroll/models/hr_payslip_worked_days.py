# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools.float_utils import float_compare


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _l10n_be_skip_amount_computation(self):
        self.ensure_one()
        return self.payslip_id.state != 'draft' \
                or self.payslip_id.edited \
                or self.payslip_id.wage_type != 'monthly' \
                or self.payslip_id.struct_id.country_id.code != 'BE' \
                or not self.is_paid

    def _l10n_be_get_LEAVE1731_amount(self):
        # For the average of the variable remuneration:
        # Taking into account the full number of months with the employer
        # Variable monthly average remuneration to be divided by 25 and increased by 20% (in 5-day regime).
        # Example: if over 7 months, the variable average monthly remuneration is € 1,212.
        # You add, to the JF, the following amount: 1212/25 = 48.48 + 20% = € 58.17.
        self.ensure_one()
        amount = self.payslip_id._get_last_year_average_variable_revenues() / 25.0
        work_time_rate = self.version_id.resource_calendar_id.work_time_rate
        if not float_compare(work_time_rate, 100, precision_digits=2):
            amount *= 1.2
        if self.payslip_id.id:
            worked_day_line_values = self.payslip_id._get_worked_days_line_values(
                ['LEAVE500'], ['number_of_days'], compute_sum=True
            )
            number_of_days = worked_day_line_values['LEAVE500']['sum']['number_of_days']
        else:
            number_of_days = self.payslip_id._get_worked_days_line_values_orm('LEAVE500', 'number_of_days')
        return amount * number_of_days

    def _l10n_be_get_LEAVE260_amount(self, wage):
        # For training time off: The maximum reimbursement is fixed by a threshold that you can
        # find at https://www.leforem.be/entreprises/aides-financieres-conge-education-paye.html
        # In that case we have to adapt the wage.
        self.ensure_one()
        wage_to_deduct = 0
        max_hours_per_week = self.version_id.standard_calendar_id.hours_per_week \
                                or self.version_id.resource_calendar_id.hours_per_week
        training_ratio = 3 / (13 * max_hours_per_week) if max_hours_per_week else 0
        training_hours = sum(self.payslip_id.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code == 'LEAVE260'
        ).mapped('number_of_hours'))
        training_threshold = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
            'training_time_off_threshold', self.payslip_id.date_to, raise_if_not_found=False)
        if wage > training_threshold:
            hourly_wage_to_deduct = (wage - training_threshold) * training_ratio
            wage_to_deduct = training_hours * hourly_wage_to_deduct
        if wage_to_deduct:
            return min(wage, training_threshold) * training_ratio * training_hours
        else:
            hours_per_week = self.payslip_id._get_worked_day_lines_hours_per_week()
            return wage * 3 / (13 * hours_per_week) * training_hours if hours_per_week else 0

    def _l10n_be_has_enough_paid_hours(self):
        # We usually deduct the unpaid hours using the hourly formula. This is the fairest
        # way to deduct 1 day, because we will deduct the same amount in a short month (February)
        # than in a long month (March)
        # But in the case of the long month with not enough paid hours, this could lead
        # to a basic salary = 0, which is in that case unfair. Switch to another method in which
        # we compute the amount from the paid hours using the hourly formula
        self.ensure_one()
        excluded_work_entry_codes = ['OUT', 'LEAVE300', 'LEAVE301', 'MEDIC01']
        paid_hours = sum(self.payslip_id.worked_days_line_ids.filtered(
            lambda wd: wd.is_paid and wd.work_entry_type_id.code not in excluded_work_entry_codes
        ).mapped('number_of_hours'))
        hours_per_week = self.payslip_id._get_worked_day_lines_hours_per_week()
        return paid_hours >= hours_per_week or self.work_entry_type_id.code in excluded_work_entry_codes

    def _l10n_be_get_paid_work_days(self):
        self.ensure_one()
        payslip = self.payslip_id
        worked_days_line_ids = payslip.worked_days_line_ids
        excluded_work_entry_codes = [
            'OUT', 'LEAVE300', 'LEAVE301', 'LEAVE260', 'LEAVE216',
            'LEAVE1731', 'LEAVE6665', 'LEAVE214', 'MEDIC01'
        ]
        paid_worked_days = worked_days_line_ids.filtered(
            lambda wd: wd.is_paid and wd.code not in excluded_work_entry_codes
        ).sorted('number_of_hours', reverse=True)
        if not paid_worked_days:
            # In case there is only european time off for instance
            paid_worked_days = worked_days_line_ids.filtered(
                lambda wd: wd.is_paid and wd.code not in ['LEAVE300', 'LEAVE301', 'MEDIC01'])
        return paid_worked_days

    def _l10n_be_get_amount_ratio(self, number_of_hours, out_ratio):
        self.ensure_one()
        hours_per_week = self.payslip_id._get_worked_day_lines_hours_per_week()
        ratio = 3 / (13 * hours_per_week) * number_of_hours if hours_per_week else 0 # (3 months = 13 weeks)
        if out_ratio != None:
            ratio = out_ratio - ratio
        return ratio

    def _l10n_be_get_workday_amount(self, wage, nb_hour=None, out_ratio=None, inverse=False):
        self.ensure_one()
        number_of_hours = nb_hour if nb_hour != None else self.number_of_hours
        ratio = self._l10n_be_get_amount_ratio(number_of_hours, out_ratio)
        return ratio * wage if not inverse else (1-ratio) * wage

    def _l10n_be_get_out_ratio(self):
        self.ensure_one()
        out_worked_day = self.payslip_id.worked_days_line_ids.filtered(lambda wd: wd.code == 'OUT')
        if out_worked_day:
            out_hours = sum(out_worked_day.mapped('number_of_hours'))
            out_hours_per_week = self.payslip_id._get_out_of_contract_calendar().hours_per_week
            return 1 - 3 / (13 * out_hours_per_week) * out_hours if out_hours_per_week else 1
        return 1

    def _compute_amount(self):
        computed_by_super = self.env['hr.payslip.worked_days']
        for worked_day in self:

            wage = worked_day.version_id._get_contract_wage() if worked_day.version_id else 0

            if worked_day._l10n_be_skip_amount_computation():
                computed_by_super += worked_day
                continue
            if worked_day.work_entry_type_id.l10n_be_is_time_credit or worked_day.code == 'OUT':
                worked_day.amount = 0
                continue
            if worked_day.code == 'LEAVE1731':
                worked_day.amount = worked_day._l10n_be_get_LEAVE1731_amount()
                continue
            if not worked_day._l10n_be_has_enough_paid_hours():
                worked_day.amount = worked_day._l10n_be_get_workday_amount(wage)
                continue
            if worked_day.code == 'LEAVE260':
                worked_day.amount = worked_day._l10n_be_get_LEAVE260_amount(wage)
                continue

            ####################################################################################
            #  Example:
            #  Note: (3/13/38) * wage : hourly wage, if 13th months and 38 hours/week calendar
            #
            #  CODE     :   number_of_hours    :    Amount
            #  WORK100  :      130 hours       : (1 - 3/13/38 * (15 + 30)) * wage
            #  PAID     :      30 hours        : 3/13/38 * (15 + 30)) * wage
            #  UNPAID   :      15 hours        : 0
            #
            #  TOTAL PAID : WORK100 + PAID + UNPAID = (1 - 3/13/38 * 15 ) * wage
            ####################################################################################
            paid_worked_days = worked_day._l10n_be_get_paid_work_days()
            main_worked_day = paid_worked_days[0].code if paid_worked_days else False
            amount_rate = worked_day.work_entry_type_id.amount_rate

            if worked_day.code != main_worked_day:
                worked_day.amount = min(wage, worked_day._l10n_be_get_workday_amount(wage)) * amount_rate
                continue

            # If out of contract, we use the hourly formula to deduct the real wage
            out_ratio = worked_day._l10n_be_get_out_ratio()

            # WORK100 (Generally)
            worked_days_line_ids = worked_day.payslip_id.worked_days_line_ids
            work100_wds = worked_days_line_ids.filtered(lambda wd: wd.code == main_worked_day)
            number_of_other_hours = sum(
                wd.number_of_hours
                for wd in worked_days_line_ids
                if wd.code not in [main_worked_day, 'OUT']
                and not wd.work_entry_type_id.l10n_be_is_time_credit
                and not wd.work_entry_type_id.is_extra_hours
            )

            if len(work100_wds) == 1:
                worked_day.amount = max(
                    0, worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                ) * amount_rate
                continue

            # Case with half days mixed with full days
            # If only presence -> Compute the full days from the hourly formula
            if len(set(worked_days_line_ids.mapped('code'))) == 1:
                wage = worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                if float_compare(worked_day.number_of_hours, max(work100_wds.mapped('number_of_hours')), 2): # lowest lines
                    number_of_hours = (work100_wds - worked_day).number_of_hours
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage, number_of_hours, inverse=True) * amount_rate
                    continue
                else:  # biggest line
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage) * amount_rate
                    continue
            # Mix of presence/absences - Compute the half days from the hourly formula
            else:
                if float_compare(worked_day.number_of_hours, max(work100_wds.mapped('number_of_hours')), 2): # lowest lines
                    worked_day.amount = worked_day._l10n_be_get_workday_amount(wage) * amount_rate
                    continue
                else:  # biggest line
                    total_wage = worked_day._l10n_be_get_workday_amount(wage, number_of_other_hours, out_ratio)
                    number_of_hours = (work100_wds - worked_day).number_of_hours
                    worked_day.amount = (total_wage - worked_day._l10n_be_get_workday_amount(wage, number_of_hours)) * amount_rate
                    continue

        super(HrPayslipWorkedDays, computed_by_super)._compute_amount()
