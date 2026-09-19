# Part of Odoo. See LICENSE file for full copyright and licensing details.

from pytz import timezone
from dateutil.relativedelta import relativedelta, MO, SU
from dateutil import rrule
from calendar import monthrange
from collections import defaultdict, Counter
from datetime import date, timedelta
from itertools import chain

from odoo import api, Command, models, fields, _
from odoo.tools import SQL, float_round, float_is_zero, ormcache


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    meal_voucher_count = fields.Integer(
        compute='_compute_work_entry_dependent_benefits')  # Overrides compute method
    # YTI NOTE: Changed nature of field (from missing dats to granting days)
    private_car_missing_days = fields.Integer(
        string='Days Granting Private Car Reimbursement',
        compute='_compute_work_entry_dependent_benefits')
    representation_fees_missing_days = fields.Integer(
        string='Days Not Granting Representation Fees',
        compute='_compute_work_entry_dependent_benefits')
    l10n_be_is_double_pay = fields.Boolean(compute='_compute_l10n_be_is_double_pay')
    l10n_be_max_seizable_amount = fields.Float(compute='_compute_l10n_be_max_seizable_amount')
    l10n_be_max_seizable_warning = fields.Char(compute='_compute_l10n_be_max_seizable_amount')
    l10n_be_is_december = fields.Boolean(compute='_compute_l10n_be_is_december')
    l10n_be_has_eco_vouchers = fields.Boolean(compute='_compute_l10n_be_has_eco_vouchers', search='_search_l10n_be_has_eco_vouchers')

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_input_line_ids(self):
        res = super()._compute_input_line_ids()
        balance_by_employee = self._get_salary_advance_balances()
        for slip in self:
            if not slip.employee_id or not slip.date_from or not slip.date_to or slip.country_code != 'BE':
                continue
            # If a double holiday pay should be recovered
            if slip.struct_id.code == 'CP200DOUBLE':
                to_recover = slip._get_sum_european_time_off_days()
                if to_recover:
                    european_type = self.env.ref('l10n_be_hr_payroll.input_double_holiday_european_leave_deduction')
                    lines_to_remove = slip.input_line_ids.filtered(lambda x: x.input_type_id == european_type)
                    to_remove_vals = [(3, line.id, False) for line in lines_to_remove]
                    to_add_vals = [(0, 0, {
                        'name': _('European Leaves Deduction'),
                        'amount': to_recover,
                        'input_type_id': european_type.id,
                    })]
                    slip.write({'input_line_ids': to_remove_vals + to_add_vals})
            elif slip.struct_id.code == 'CP200SALARYADV':
                sal_adv_type = self.env.ref('l10n_be_hr_payroll.input_salary_advance')
                sal_adv_rec_type = self.env.ref('l10n_be_hr_payroll.cp200_input_advance')
                lines_to_remove = slip.input_line_ids.filtered(lambda x: x.input_type_id in (sal_adv_type, sal_adv_rec_type))
                to_remove_vals = [(3, line.id, False) for line in lines_to_remove]
                to_add_vals = [(0, 0, {
                    'name': _('Salary Advance'),
                    'amount': 0,
                    'input_type_id': sal_adv_type.id,
                })]
                slip.write({'input_line_ids': to_remove_vals + to_add_vals})
            elif slip.struct_id.code == 'CP200MONTHLY':
                balance = balance_by_employee[slip.employee_id]
                if balance <= 0:
                    continue
                sal_adv_type = self.env.ref('l10n_be_hr_payroll.input_salary_advance')
                sal_adv_rec_type = self.env.ref('l10n_be_hr_payroll.cp200_input_advance')
                lines_to_remove = slip.input_line_ids.filtered(
                    lambda x: x.input_type_id in (sal_adv_rec_type, sal_adv_type)
                )
                to_remove_vals = [(3, line.id, False) for line in lines_to_remove]
                to_add_vals = [(0, 0, {
                    'name': _('Salary Advance Recovery'),
                    'amount': balance,
                    'input_type_id': sal_adv_rec_type.id,
                })]
                slip.write({'input_line_ids': to_remove_vals + to_add_vals})
            elif slip.struct_id.code == 'CP200CCT90':
                cct90_input_type = self.env.ref('l10n_be_hr_payroll.input_cct90_bonus_plan')
                lines_to_remove = slip.input_line_ids.filtered(lambda x: x.input_type_id == cct90_input_type)
                to_remove_vals = [Command.unlink(line.id) for line in lines_to_remove]
                to_add_vals = [Command.create({
                    'name': _('CCT90 Bonus Plan'),
                    'amount': 0,
                    'input_type_id': cct90_input_type.id,
                })]
                slip.write({'input_line_ids': to_remove_vals + to_add_vals})
        return res

    @ormcache('self.employee_id', 'self.date_from', 'self.date_to')
    def _get_period_contracts(self):
        # Returns all the employee contracts over the same payslip period, to avoid
        # double remunerations for some line codes
        self.ensure_one()
        if self.env.context.get('salary_simulation'):
            return self.env.context['origin_version_id']
        contracts = self.employee_id._get_versions_with_contract_overlap_with_period(
            self.date_from,
            self.date_to,
        ).sorted('date_start')
        return contracts.ids

    def _get_max_basic_salary_contract(self, contracts):
        self.ensure_one()
        if len(contracts) == 1:
            return contracts
        credit_time_work_entry_type_ids = [
            self.env['ir.model.data']._xmlid_to_res_model_res_id('hr_work_entry.l10n_be_work_entry_type_credit_time')[1],
            self.env['ir.model.data']._xmlid_to_res_model_res_id('hr_work_entry.l10n_be_work_entry_type_parental_time_off')[1],
        ]
        unpaid_work_entry_types = self.struct_id.unpaid_work_entry_type_ids.ids + credit_time_work_entry_type_ids
        for contract in contracts:
            date_end = min([contract.date_end, self.date_to]) if contract.date_end else self.date_to
            all_work_hours = contract.get_work_hours(self.date_from, date_end)
            work_hours = sum(
                hours for work_entry_type_id, hours in all_work_hours.items() \
                if work_entry_type_id not in unpaid_work_entry_types)
            if not float_is_zero(work_hours, precision_digits=2):
                return contract
        return contracts[0]

    @api.depends('worked_days_line_ids.number_of_hours', 'worked_days_line_ids.is_paid',
                'worked_days_line_ids.work_entry_type_id.l10n_be_is_time_credit')
    def _compute_worked_hours(self):
        super()._compute_worked_hours()
        for payslip in self:
            payslip.sum_worked_hours -= sum(
                line.number_of_hours for line in payslip.worked_days_line_ids
                    if line.work_entry_type_id.l10n_be_is_time_credit
            )

    @api.depends('struct_id', 'date_from')
    def _compute_l10n_be_is_december(self):
        for payslip in self:
            payslip.l10n_be_is_december = payslip.struct_id.code == "CP200MONTHLY" and payslip.date_from and payslip.date_from.month == 12

    def _compute_work_entry_dependent_benefits(self):
        if self.env.context.get('salary_simulation'):
            for payslip in self:
                payslip.meal_voucher_count = 20
                payslip.private_car_missing_days = 20
                payslip.representation_fees_missing_days = 0
        else:
            all_benefits = self.env['hr.work.entry.type'].get_work_entry_type_benefits()
            query = self.env['l10n_be.work.entry.daily.benefit.report']._search([
                ('employee_id', 'in', self.mapped('employee_id').ids),
                ('day', '<=', max(self.mapped('date_to'))),
                ('day', '>=', min(self.mapped('date_from'))),
            ])
            work_entries_benefits_rights = self.env.execute_query_dict(
                query.select('day', 'benefit_name', 'employee_id'))

            work_entries_benefits_rights_by_employee = defaultdict(list)
            for work_entries_benefits_right in work_entries_benefits_rights:
                employee_id = work_entries_benefits_right['employee_id']
                work_entries_benefits_rights_by_employee[employee_id].append(work_entries_benefits_right)

            # {(calendar, date_from, date_to): resources}
            mapped_resources = defaultdict(lambda: self.env['resource.resource'])
            for payslip in self:
                contract = payslip.version_id
                calendar = contract.resource_calendar_id if not contract.l10n_be_time_credit else contract.standard_calendar_id
                mapped_resources[(calendar, payslip.date_from, payslip.date_to)] |= contract.employee_id.resource_id
            # {(calendar, date_from, date_to): intervals}}
            mapped_intervals = {}
            for (calendar, date_from, date_to), resources in mapped_resources.items():
                tz = timezone(calendar.tz)
                mapped_intervals[(calendar, date_from, date_to)] = calendar._attendance_intervals_batch(
                    tz.localize(fields.Datetime.to_datetime(date_from)),
                    tz.localize(fields.Datetime.to_datetime(date_to) + timedelta(days=1, seconds=-1)),
                    resources=resources, tz=tz)

            for payslip in self:
                contract = payslip.version_id
                benefits = dict.fromkeys(all_benefits, 0)
                date_from = max(payslip.date_from, contract.date_start)
                date_to = min(payslip.date_to, contract.date_end or payslip.date_to)
                for work_entries_benefits_right in (
                        work_entries_benefits_right
                        for work_entries_benefits_right in work_entries_benefits_rights_by_employee[payslip.employee_id.id]
                        if date_from <= work_entries_benefits_right['day'] <= date_to
                    ):
                    if work_entries_benefits_right['benefit_name'] not in benefits:
                        benefits[work_entries_benefits_right['benefit_name']] = 1
                    else:
                        benefits[work_entries_benefits_right['benefit_name']] += 1

                contract = payslip.version_id
                resource = contract.employee_id.resource_id
                calendar = contract.resource_calendar_id if not contract.l10n_be_time_credit else contract.standard_calendar_id
                intervals = mapped_intervals[(calendar, payslip.date_from, payslip.date_to)][resource.id]

                nb_of_days_to_work = len({dt_from.date(): True for (dt_from, dt_to, attendance) in intervals})
                payslip.private_car_missing_days = benefits['private_car'] if 'private_car' in benefits else 0
                payslip.representation_fees_missing_days = nb_of_days_to_work - (benefits['representation_fees'] if 'representation_fees' in benefits else 0)
                payslip.meal_voucher_count = benefits['meal_voucher']

    @api.depends('struct_id')
    def _compute_l10n_be_is_double_pay(self):
        for payslip in self:
            payslip.l10n_be_is_double_pay = payslip.struct_id.code == "CP200DOUBLE"

    @api.depends('input_line_ids')
    def _compute_l10n_be_has_eco_vouchers(self):
        for slip in self:
            slip.l10n_be_has_eco_vouchers = any(input_line.code == 'ECOVOUCHERS' for input_line in slip.input_line_ids)

    def _search_l10n_be_has_eco_vouchers(self, operator, value):
        if operator != 'in':
            return NotImplemented
        rows = self.env.execute_query(SQL("""
            SELECT id
            FROM hr_payslip payslip
            WHERE EXISTS
                (SELECT 1
                 FROM   hr_payslip_input hpi
                 JOIN   hr_payslip_input_type hpit
                 ON     hpi.input_type_id = hpit.id AND hpit.code = 'ECOVOUCHERS'
                 WHERE  hpi.payslip_id = payslip.id
                 LIMIT  1)
        """))
        return [('id', 'in', [r[0] for r in rows])]

    @api.depends('date_to', 'line_ids.total', 'input_line_ids.code')
    def _compute_l10n_be_max_seizable_amount(self):
        # Source: https://emploi.belgique.be/fr/themes/remuneration/protection-de-la-remuneration/saisie-et-cession-sur-salaires
        all_payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', self.employee_id.ids),
            ('state', '!=', 'cancel')])
        payslip_values = all_payslips._get_line_values(['NET'])
        for payslip in self:
            if payslip.struct_id.country_id.code != 'BE':
                payslip.l10n_be_max_seizable_amount = 0
                payslip.l10n_be_max_seizable_warning = False
                continue

            rates = self.env['hr.rule.parameter']._get_parameter_from_code('cp200_seizable_percentages', payslip.date_to, raise_if_not_found=False)
            child_increase = self.env['hr.rule.parameter']._get_parameter_from_code('cp200_seizable_amount_child', payslip.date_to, raise_if_not_found=False)
            if not rates or not child_increase:
                payslip.l10n_be_max_seizable_amount = 0
                payslip.l10n_be_max_seizable_warning = False
                continue

            # Note: the ceiling amounts are based on the net revenues
            period_payslips = all_payslips.filtered(
                lambda p: p.employee_id == payslip.employee_id and p.date_from == payslip.date_from and p.date_to == payslip.date_to)
            net_amount = sum([payslip_values['NET'][p.id]['total'] for p in period_payslips])
            seized_amount = sum([period_payslips._get_input_line_amount(code) for code in ['ATTACH_SALARY', 'ASSIG_SALARY', 'CHILD_SUPPORT']])
            net_amount += seized_amount
            # Note: The reduction for dependant children is not applied most of the time because
            #       the process is too complex.
            # To benefit from this increase in the elusive or non-transferable quotas, the worker
            # whose remuneration is subject to seizure or transfer, must declare it using a form,
            # the model of which has been published in the Belgian Official Gazette. of 30 November
            # 2006.
            # He must attach to this form the documents establishing the reality of the
            # charge invoked.
            # Source: Opinion on the indexation of the amounts set in Article 1, paragraph 4, of
            # the Royal Decree of 27 December 2004 implementing Articles 1409, § 1, paragraph 4,
            # and 1409, § 1 bis, paragraph 4 , of the Judicial Code relating to the limitation of
            # seizure when there are dependent children, MB, December 13, 2019.
            dependent_children = payslip.employee_id.l10n_be_dependent_children_attachment
            max_seizable_amount = 0
            for left, right, rate in rates:
                if dependent_children:
                    left += dependent_children * child_increase
                    right += dependent_children * child_increase
                if left <= net_amount:
                    max_seizable_amount += (min(net_amount, right) - left) * rate
            payslip.l10n_be_max_seizable_amount = max_seizable_amount
            if max_seizable_amount and seized_amount > max_seizable_amount:
                payslip.l10n_be_max_seizable_warning = _(
                    'The seized amount (%(seized_amount)s€) is above the belgian ceilings. Given a global net salary of %(net_amount)s€ for the pay period and %(dependent_children)s dependent children, the maximum seizable amount is equal to %(max_seizable_amount)s€',
                    seized_amount=round(seized_amount, 2),
                    net_amount=round(net_amount, 2),
                    dependent_children=round(dependent_children, 2),
                    max_seizable_amount=round(max_seizable_amount, 2),
                )
            else:
                payslip.l10n_be_max_seizable_warning = False

    def _get_salary_advance_balances(self):
        balance_by_employee = super()._get_salary_advance_balances()
        payslips_by_employee = self._read_group(
            domain=[
                ('struct_id.country_id', '=', 'BE'),
                ('state', 'in', ('validated', 'paid')),
                ('employee_id', 'in', self.employee_id.ids),
                ('input_line_ids.code', 'in', ('SALARYADVREC', 'SALARYADV')),
            ],
            groupby=['employee_id'],
            aggregates=['id:recordset']
        )
        for employee_id, payslips in payslips_by_employee:
            for input_line in chain.from_iterable(payslip.input_line_ids for payslip in payslips):
                if input_line.code == 'SALARYADV':
                    balance_by_employee[employee_id] += input_line.amount
                elif input_line.code == 'SALARYADVREC':
                    balance_by_employee[employee_id] -= input_line.amount
        return balance_by_employee

    def _get_worked_day_lines_hours_per_day(self):
        self.ensure_one()
        if self.version_id.l10n_be_time_credit:
            return self.version_id.standard_calendar_id.hours_per_day
        return super()._get_worked_day_lines_hours_per_day()

    def _get_out_of_contract_calendar(self):
        self.ensure_one()
        if self.version_id.l10n_be_time_credit:
            return self.version_id.standard_calendar_id
        return super()._get_out_of_contract_calendar()

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        res = []
        if self.struct_id.country_id.code != 'BE':
            return super()._get_worked_day_lines_values(domain=domain)
        # If a belgian payslip has half-day attendances/time off, it the worked days lines should
        # be separated
        work_hours = self.version_id._get_work_hours_split_half(self.date_from, self.date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        for worked_days_data, duration_data in work_hours_ordered:
            duration_type, work_entry_type_id = worked_days_data
            number_of_days, number_of_hours = duration_data
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            attendance_line = {
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type_id,
                'number_of_days': number_of_days,
                'number_of_hours': number_of_hours,
            }
            res.append(attendance_line)
        # If there is a public holiday less than 30 days after the end of the contract
        # this public holiday should be taken into account in the worked days lines
        if self.version_id.date_end and self.date_from <= self.version_id.date_end <= self.date_to:
            # If the contract is followed by another one (eg. after an appraisal)
            if self.version_id.employee_id.version_ids.filtered(lambda v: v.date_start > self.version_id.date_end):
                return res
            public_holiday_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday')
            public_leaves = self.version_id.resource_calendar_id.global_leave_ids.filtered(
                lambda l: l.work_entry_type_id == public_holiday_type)
            # If less than 15 days under contract, the public holidays is not reimbursed
            public_leaves = public_leaves.filtered(
                lambda l: (l.date_from.date() - self.employee_id.contract_date_start).days >= 15)
            # If less than 15 days of occupation -> no payment of the time off after contract
            # If less than 1 month of occupation -> payment of the time off occurring within 15 days after contract.
            # Occupation = duration since the start of the contract, from date to date
            public_leaves = public_leaves.filtered(
                lambda l: 0 < (l.date_from.date() - self.version_id.date_end).days <= (30 if self.employee_id.contract_date_start + relativedelta(months=1) <= self.version_id.date_end else 15))
            if public_leaves:
                input_type_id = self.env.ref('l10n_be_hr_payroll.cp200_other_input_after_contract_public_holidays').id
                if input_type_id not in self.input_line_ids.mapped('input_type_id').ids:
                    self.write({'input_line_ids': [(0, 0, {
                        'name': _('After Contract Public Holidays'),
                        'amount': 0.0,
                        'input_type_id': self.env.ref('l10n_be_hr_payroll.cp200_other_input_after_contract_public_holidays').id,
                    })]})
        # Handle loss on commissions
        if self._get_last_year_average_variable_revenues():
            we_types_ids = (
                self.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday') + self.env.ref('hr_work_entry.l10n_be_work_entry_type_small_unemployment')
            ).ids
            # if self.worked_days_line_ids.filtered(lambda wd: wd.code in ['LEAVE205', 'LEAVE500']):
            if any(line_vals['work_entry_type_id'] in we_types_ids for line_vals in res):
                we_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_simple_holiday_pay_variable_salary')
                res.append({
                    'sequence': we_type.sequence,
                    'work_entry_type_id': we_type.id,
                    'number_of_days': 0,
                    'number_of_hours': 0,
                })
        return res

    def _get_last_year_average_variable_revenues(self):
        date_from = self.env.context.get('variable_revenue_date_from', self.date_from)
        first_version_date = self.employee_id._get_first_version_date()
        if not first_version_date:
            return 0
        start = first_version_date
        end = date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        if number_of_month <= 0:
            return 0
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('date_from', '>=', date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<=', date_from),
        ], order="date_from asc")
        total_amount = payslips._get_line_values(['COMMISSION'], compute_sum=True)['COMMISSION']['sum']['total']
        return total_amount / number_of_month if number_of_month else 0

    def _get_last_year_average_warrant_revenues(self):
        warrant_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['validated', 'paid']),
            ('struct_id.code', '=', 'CP200WARRANT'),
            ('date_from', '>=', self.date_from + relativedelta(months=-12, day=1)),
            ('date_from', '<', self.date_from),
        ], order="date_from asc")
        total_amount = warrant_payslips._get_line_values(['BASIC'], compute_sum=True)['BASIC']['sum']['total']
        first_version_date = self.employee_id._get_first_version_date()
        if not first_version_date:
            return 0
        # Only complete months count
        if first_version_date.day != 1:
            start = first_version_date + relativedelta(day=1, months=1)
        else:
            start = first_version_date
        end = self.date_from + relativedelta(day=31, months=-1)
        number_of_month = (end.year - start.year) * 12 + (end.month - start.month) + 1
        number_of_month = min(12, number_of_month)
        return total_amount / number_of_month if number_of_month else 0

    def _compute_number_complete_months_of_work(self, date_from, date_to, contracts, use_work_rate=False):
        days_by_contract_by_year = defaultdict(lambda: defaultdict(dict))
        for day in rrule.rrule(rrule.DAILY, dtstart=date_from + relativedelta(day=1), until=date_to + relativedelta(day=31)):
            days_by_contract_by_year[day.year][day.month][day.date()] = None

        public_holidays = [(leave.date_from.date(), leave.date_to.date()) for leave in self.employee_id._get_public_holidays(date_from, date_to)]
        for contract in contracts:
            work_days = {int(d) for d in contract.resource_calendar_id._get_global_attendances().mapped('dayofweek')}

            previous_week_start = max(contract.date_start + relativedelta(weeks=-1, weekday=MO(-1)), date_from + relativedelta(day=1))
            next_week_end = min(contract.date_end + relativedelta(weeks=+1, weekday=SU(+1)) if contract.date_end else date.max, date_to)
            days_to_check = rrule.rrule(rrule.DAILY, dtstart=previous_week_start, until=next_week_end)
            for day in days_to_check:
                day = day.date()

                # Full time credit time doesn't count
                if contract.l10n_be_time_credit and not contract.work_time_rate:
                    continue
                if contract.date_start <= day <= (contract.date_end or date.max):
                    days_by_contract_by_year[day.year][day.month][day] = contract
                elif (day.weekday() not in work_days or
                        any(date_from <= day <= date_to for date_from, date_to in public_holidays)):
                    days_by_contract_by_year[day.year][day.month][day] = 'holiday'

        months = 0
        for invalid_days_by_months in days_by_contract_by_year.values():
            for days in invalid_days_by_months.values():
                counter = Counter(days.values())
                if None in counter:
                    continue
                if use_work_rate:
                    under_contract_days = sum(counter.values()) - counter.pop('holiday', 0)
                    for contract, n_days in counter.items():
                        months += n_days / under_contract_days * contract.work_time_rate
                else:
                    months += 1
        return months

    def _compute_presence_prorated_fixed_wage(self, date_from, date_to, versions):
        self.ensure_one()

        def _get_calendar_days(leave, date_min, date_max):
            date_from = max(date_min, leave.date_from.date())
            date_to = min(date_max, leave.date_to.date())
            days = (date_to - date_from).days + 1
            if leave.request_unit_half:
                if leave.request_date_from_period == leave.request_date_to_period:
                    return days - 0.5
                elif leave.request_date_from_period == 'pm' and leave.request_date_to_period == 'am':
                    return days - 1
            return days

        def round_half_days(duration):
            return round(duration * 2) / 2

        work_entries = self.env['hr.work.entry'].search([
            ('state', 'in', ['validated', 'draft']),
            ('employee_id', '=', self.employee_id.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ], order="date asc")
        work_entries_by_date = work_entries.grouped('date')
        unpaid_work_entry_types = self.env['hr.work.entry.type']
        unpaid_leave_type = self.env.ref('hr_work_entry.work_entry_type_unpaid_leave', raise_if_not_found=False)
        if unpaid_leave_type:
            unpaid_work_entry_types += unpaid_leave_type
        unjustified_reason_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_unjustified_reason', raise_if_not_found=False)
        if unjustified_reason_type:
            unpaid_work_entry_types += unjustified_reason_type
        is_PFA = self.struct_id.code == 'CP200THIRTEEN'
        fte_basic = self.version_id._get_contract_wage() * 1 / self.version_id.work_time_rate if self.version_id.work_time_rate else 0
        company_avg_hours_per_day = self.company_id.resource_calendar_id.hours_per_day

        version_by_date = defaultdict(lambda: defaultdict(dict))
        for day in rrule.rrule(rrule.DAILY, dtstart=date_from + relativedelta(day=1), until=date_to + relativedelta(day=31)):
            version_by_date[day.year][day.month][day.date()] = None

        full_unpaid_months = set()
        for version in versions:
            working_days = version.resource_calendar_id._get_working_hours()

            # As version changes can go from friday to monday, we need to extend the search to the previous monday/next sunday
            # We only check for next sunday for the last version otherwise we would write the wrong version
            previous_week_start = max(version.date_start + relativedelta(weeks=-1, weekday=MO(-1)), date_from + relativedelta(day=1))
            if version == versions[-1]:
                date_end = min(version.date_end + relativedelta(weeks=+1, weekday=SU(+1)) if version.date_end else date.max, date_to)
            else:
                date_end = min(version.date_end or date.max, date_to)
            days_to_check = rrule.rrule(rrule.DAILY, dtstart=previous_week_start, until=date_end)

            for day in days_to_check:
                day = day.date()
                work_entries_date = work_entries_by_date.get(day)

                if version_by_date[day.year][day.month][day] or day.month in full_unpaid_months:
                    continue

                dayofweek = str(day.weekday())
                if version.resource_calendar_id.two_weeks_calendar:
                    weektype = str(self.env['resource.calendar.attendance'].get_week_type(day))
                    is_calendar_day = working_days[weektype][dayofweek]
                else:
                    is_calendar_day = working_days[False][dayofweek]

                if is_calendar_day and (not work_entries_date or (is_PFA and all(we.work_entry_type_id in unpaid_work_entry_types for we in work_entries_date))):
                    full_unpaid_months.add(day.month)
                else:
                    version_by_date[day.year][day.month][day] = version

        full_time_months = 0
        payslip_amount = 0

        ### PFA STUFF ###
        sick_work_entry_type_codes = [
            'LEAVE110',  # Sick Time Off
            'LEAVE280',  # Long Term Sick
            'LEAVE214',  # Sick Time Off (Without Guaranteed Salary)
            'LEAVE281',  # Partial Incapacity
        ]
        covered_time_offs = self.env['hr.leave']
        pfa_calendar_sick_days_remaining = 60
        pfa_sick_calendar_days_to_defer = 0  # used to report time off to deduct to next month
        pfa_unpredictable_days_remaining = 10
        sick_work_entries = work_entries.filtered_domain([
            ('work_entry_type_id.code', 'in', sick_work_entry_type_codes)
        ])
        unpredictable_work_entries = work_entries.filtered_domain([
            ('work_entry_type_id.code', '=', 'LEAVE250')
        ])

        if is_PFA:
            # If the first work entry of the year is a sick work entry, check for last year work entries
            # If already sick in december last year, we should deduct these days, except if there is a period of 14 calendar days of work
            if work_entries and work_entries[0].work_entry_type_id.code in sick_work_entry_type_codes:
                last_year_work_entries = self.env['hr.work.entry'].search([
                    ('state', 'in', ['draft', 'validated']),
                    ('employee_id', '=', self.employee_id.id),
                    ('date', '>=', date_from - relativedelta(years=1)),
                    ('date', '<=', date_to - relativedelta(years=1)),
                ], order="date asc")
                if last_year_work_entries and last_year_work_entries[-1].work_entry_type_id.code in sick_work_entry_type_codes:
                    last_year_sick_work_entries = last_year_work_entries.filtered_domain([
                        ('work_entry_type_id.code', 'in', sick_work_entry_type_codes)
                    ])
                    # Check if has worked for 14 consecutive days. If yes, then do not deduct last year sick days
                    # We ignore half days of sickness, as sick time off are not taken in half days in Belgium
                    has_worked_consecutive_14_days = False
                    consecutive_work_days_counter = 0
                    current_date = date_from
                    while current_date < date_to:
                        work_entries = work_entries_by_date.get(current_date)
                        if not work_entries or any(we.work_entry_type_id.code not in sick_work_entry_type_codes for we in work_entries):
                            consecutive_work_days_counter += 1
                        else:
                            consecutive_work_days_counter = 0
                            if leave_work_entries := work_entries.filtered('leave_id'):
                                current_date = max(leave_work_entries.leave_id.mapped('date_to')).date() + relativedelta(days=1)
                                continue

                        # If worked 14 calendar consecutive days, counter is set to 60 days for the year
                        if consecutive_work_days_counter >= 14:
                            has_worked_consecutive_14_days = True
                            break
                        current_date += relativedelta(days=1)

                    if not has_worked_consecutive_14_days:
                        last_year_sick_calendar_days = 0
                        last_year_covered_time_offs = self.env['hr.leave']
                        for sick_wes in last_year_sick_work_entries.grouped('date').values():
                            for sick_we in sick_wes:
                                if sick_we.leave_id and not sick_we.leave_id in last_year_covered_time_offs:
                                    last_year_sick_calendar_days += _get_calendar_days(
                                       sick_we.leave_id, date_from - relativedelta(years=1), date_to - relativedelta(years=1)
                                    )
                                    last_year_covered_time_offs |= sick_we.leave_id
                                elif not sick_we.leave_id:
                                    last_year_sick_calendar_days += round_half_days(sick_we.duration / company_avg_hours_per_day)

                        pfa_calendar_sick_days_remaining = max(0, pfa_calendar_sick_days_remaining - last_year_sick_calendar_days)

        for year, versions_by_month in version_by_date.items():
            for month, version_by_day in versions_by_month.items():
                days_by_version_counter = Counter(version_by_day.values())
                if None in days_by_version_counter or month in full_unpaid_months:
                    continue

                full_time_months += 1
                days_in_month = monthrange(year, month)[1]
                monthly_calendar_sick_time_off_days = 0
                monthly_covered_time_offs = self.env['hr.leave']
                for version, n_days in days_by_version_counter.items():
                    if is_PFA:
                        month_sick_work_entries = sick_work_entries.filtered(
                            lambda we: we.date.month == month and we.version_id == version
                        )
                        calendar_sick_time_off_days = 0
                        for sick_wes in month_sick_work_entries.grouped('date').values():
                            for sick_we in sick_wes:
                                if sick_we.leave_id and not sick_we.leave_id in covered_time_offs:
                                    calendar_sick_time_off_days += _get_calendar_days(
                                       sick_we.leave_id, date_from, date_to
                                    )
                                    covered_time_offs |= sick_we.leave_id
                                elif not sick_we.leave_id:
                                    calendar_sick_time_off_days += round_half_days(sick_we.duration / company_avg_hours_per_day)

                                # Used to know how many days worked in month
                                if sick_we.leave_id and not sick_we.leave_id in monthly_covered_time_offs:
                                    monthly_calendar_sick_time_off_days += _get_calendar_days(
                                       sick_we.leave_id, date(year, month, 1), date(year, month, days_in_month)
                                    )
                                    monthly_covered_time_offs |= sick_we.leave_id
                                elif not sick_we.leave_id:
                                    monthly_calendar_sick_time_off_days += round_half_days(sick_we.duration / company_avg_hours_per_day)

                        month_unpredictable_work_entries = unpredictable_work_entries.filtered(lambda we: we.date.month == month)
                        unpredictable_days = len(month_unpredictable_work_entries.mapped('date'))

                        max_sick_days_to_remove = min(monthly_calendar_sick_time_off_days, calendar_sick_time_off_days)
                        sick_days_to_remove = min(n_days, pfa_sick_calendar_days_to_defer + max_sick_days_to_remove)
                        if calendar_sick_time_off_days > sick_days_to_remove:
                            pfa_sick_calendar_days_to_defer += calendar_sick_time_off_days - sick_days_to_remove
                        else:
                            pfa_sick_calendar_days_to_defer -= max(0, sick_days_to_remove - max_sick_days_to_remove)

                        # Remove sick days
                        non_assimilated_days = max(0, sick_days_to_remove - pfa_calendar_sick_days_remaining)
                        pfa_calendar_sick_days_remaining = max(0, pfa_calendar_sick_days_remaining - sick_days_to_remove)

                        # Remove unpredictable days
                        non_assimilated_days += max(0, unpredictable_days - pfa_unpredictable_days_remaining)
                        pfa_unpredictable_days_remaining = max(0, pfa_unpredictable_days_remaining - unpredictable_days)

                        n_days -= non_assimilated_days

                    work_time_rate = version.work_time_rate
                    # Compute the real work time rate if partial incapacity. Partial incapacity should count in the work time rate in the PFA
                    if is_PFA and version.l10n_be_time_credit:
                        global_attendances = version.resource_calendar_id._get_global_attendances()
                        partial_incapacity_attendances = version.resource_calendar_id.attendance_ids.filtered_domain([
                            ('display_type', '=', False),
                            ('day_period', '!=', 'lunch'),
                            ('work_entry_type_id.code', '=', 'LEAVE281')
                        ])
                        hours_per_week_ref = version.resource_calendar_id.full_time_required_hours
                        hours_per_week = sum(att.hour_to - att.hour_from for att in global_attendances + partial_incapacity_attendances)
                        work_time_rate = hours_per_week / hours_per_week_ref if hours_per_week_ref else 1

                    payslip_amount += ((n_days / days_in_month) / 12) * (fte_basic * work_time_rate)

        if is_PFA:
            first_version_date = self.employee_id._get_first_version_date()
            if first_version_date.year == self.date_from.year and first_version_date.month >= 7:
                return 0, full_time_months
        return payslip_amount, full_time_months

    def _get_paid_amount_13th_month(self):
        versions = self.employee_id.version_ids.filtered(lambda v: v.structure_type_id == self.struct_id.type_id)
        first_version_date = self.employee_id._get_first_version_date(no_gap=False)
        if not versions or not first_version_date:
            return 0.0

        if first_version_date.year == self.date_from.year and first_version_date.month > 6:
            return 0.0

        date_from = max(first_version_date, self.date_from + relativedelta(day=1, month=1))
        date_to = self.date_to + relativedelta(day=31)

        force_months = self.input_line_ids.filtered(lambda l: l.code == 'MONTHS')
        if force_months:
            n_months = force_months[0].amount
            if n_months < 6:
                return 0.0
            fixed_salary = self.version_id._get_contract_wage() * n_months / 12
        else:
            fixed_salary, _ = self._compute_presence_prorated_fixed_wage(date_from, date_to, versions)

        force_avg_variable_revenues = self.input_line_ids.filtered(lambda l: l.code == 'VARIABLE')
        if force_avg_variable_revenues:
            avg_variable_revenues = force_avg_variable_revenues[0].amount
        else:
            avg_variable_revenues = self.with_context(
                variable_revenue_date_from=self.date_from
            )._get_last_year_average_variable_revenues()
        return fixed_salary + avg_variable_revenues

    def _get_paid_amount_warrant(self):
        self.ensure_one()
        warrant_input_type = self.env.ref('l10n_be_hr_payroll.cp200_other_input_warrant')
        return sum(self.input_line_ids.filtered(lambda a: a.input_type_id == warrant_input_type).mapped('amount'))

    def _get_paid_double_holiday(self):
        self.ensure_one()
        versions = self.employee_id.version_ids.filtered(lambda v: v.structure_type_id == self.struct_id.type_id)
        if not versions:
            return 0.0

        basic = self.version_id._get_contract_wage()
        force_months = self.input_line_ids.filtered(lambda l: l.code == 'MONTHS')

        year = self.date_from.year - 1
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)

        if force_months:
            n_months = force_months[0].amount
            fixed_salary = basic * n_months / 12
        else:
            fixed_salary, n_months = self._compute_presence_prorated_fixed_wage(date_from, date_to, versions)
            if year == int(self.employee_id.first_contract_year_n1):
                for line in self.employee_id.double_pay_line_n1_ids:
                    fixed_salary += basic * line.months_count * line.occupation_rate / 100 / 12
                    n_months += line.months_count
            elif year == int(self.employee_id.first_contract_year_n):
                for line in self.employee_id.double_pay_line_n_ids:
                    fixed_salary += basic * line.months_count * line.occupation_rate / 100 / 12
                    n_months += line.months_count

        force_avg_variable_revenues = self.input_line_ids.filtered(lambda l: l.code == 'VARIABLE')
        if force_avg_variable_revenues:
            avg_variable_revenues = force_avg_variable_revenues[0].amount
        else:
            if not n_months:
                avg_variable_revenues = 0
            else:
                avg_variable_revenues = self.with_context(
                    variable_revenue_date_from=self.date_from
                )._get_last_year_average_variable_revenues()
        return fixed_salary + avg_variable_revenues

    def _get_paid_amount_cct90_bonus_plan(self):
        self.ensure_one()
        return self._get_input_line_amount('CCT90BONUSPLAN')

    def _get_paid_amount(self):
        self.ensure_one()
        belgian_payslip = self.struct_id.country_id.code == "BE"
        if belgian_payslip:
            if self.struct_id.code == 'CP200THIRTEEN':
                return self._get_paid_amount_13th_month()
            if self.struct_id.code == 'CP200WARRANT':
                return self._get_paid_amount_warrant()
            if self.struct_id.code == 'CP200DOUBLE':
                return self._get_paid_double_holiday()
            if self.struct_id.code == 'CP200CCT90':
                return self._get_paid_amount_cct90_bonus_plan()
        return super()._get_paid_amount()

    def _is_active_belgian_languages(self):
        active_langs = self.env['res.lang'].with_context(active_test=True).search([]).mapped('code')
        return any(l in active_langs for l in ["fr_BE", "fr_FR", "nl_BE", "nl_NL", "de_BE", "de_DE"])

    def _get_sum_european_time_off_days(self, check=False):
        self.ensure_one()
        two_years_payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_to', '<=', date(self.date_from.year, 12, 31)),
            ('date_from', '>=', date(self.date_from.year - 2, 1, 1)),
            ('state', 'in', ['validated', 'paid']),
        ])
        european_time_off_amount = two_years_payslips.filtered(lambda p: p.date_from.year < self.date_from.year)._get_worked_days_line_values(['LEAVE216'], ['amount'], True)['LEAVE216']['sum']['amount']
        already_recovered_amount = two_years_payslips._get_line_values(['EU.LEAVE.DEDUC'], compute_sum=True)['EU.LEAVE.DEDUC']['sum']['total']
        return european_time_off_amount + already_recovered_amount

    def _is_invalid(self):
        invalid = super()._is_invalid()
        if not invalid and self._is_active_belgian_languages():
            country = self.struct_id.country_id
            if country.code == 'BE' and self.employee_id.lang not in ["fr_BE", "fr_FR", "nl_BE", "nl_NL", "de_BE", "de_DE"]:
                return _('This document is a translation. This is not a legal document.')
        return invalid

    def _get_negative_net_input_type(self):
        self.ensure_one()
        if self.struct_id.code == 'CP200MONTHLY':
            return self.env.ref('l10n_be_hr_payroll.input_negative_net')
        return super()._get_negative_net_input_type()

    def action_payslip_done(self):
        if self._is_active_belgian_languages():
            bad_language_slips = self.filtered(
                lambda p: p.struct_id.country_id.code == "BE" and p.employee_id.lang not in ["fr_BE", "fr_FR", "nl_BE", "nl_NL", "de_BE", "de_DE"])
            if bad_language_slips:
                action = self.env['ir.actions.act_window'].\
                    _for_xml_id('l10n_be_hr_payroll.l10n_be_hr_payroll_employee_lang_wizard_action')
                ctx = dict(self.env.context)
                ctx.update({
                    'employee_ids': bad_language_slips.employee_id.ids,
                    'default_slip_ids': self.ids,
                })
                action['context'] = ctx
                return action
        return super().action_payslip_done()

    def _get_pdf_reports(self):
        res = super()._get_pdf_reports()
        report_n = self.env.ref('l10n_be_hr_payroll.action_report_termination_holidays_n')
        report_n1 = self.env.ref('l10n_be_hr_payroll.action_report_termination_holidays_n1')
        for payslip in self:
            if payslip.struct_id.code == 'CP200HOLN1':
                res[report_n1] |= payslip
            elif payslip.struct_id.code == 'CP200HOLN':
                res[report_n] |= payslip
        return res

    def _get_data_files_to_update(self):
        # Note: file order should be maintained
        return super()._get_data_files_to_update() + [(
            'l10n_be_hr_payroll', [
                'data/hr_rule_parameters_data.xml',
            ])]

    def _get_ffe_contribution_rate(self, worker_count):
        # Fond de fermeture d'entreprise
        # https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/special_contributions/other_specialcontributions/basiccontributions_closingcompanyfunds.html
        self.ensure_one()
        if self.company_id.l10n_be_ffe_employer_type == 'commercial':
            if worker_count < 20:
                rate = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_ffe_commercial_rate_low', self.date_to)
            else:
                rate = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_ffe_commercial_rate_high', self.date_to)
        else:
            rate = self.env['hr.rule.parameter']._get_parameter_from_code('l10n_be_ffe_noncommercial_rate', self.date_to)
        return rate

    def _get_be_termination_withholding_rate(self, localdict):
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument
        self.ensure_one()

        def find_rates(x, rates):
            low_bound, high_bound = rates[0][0], rates[-1][1]
            x = min(max(low_bound, x), high_bound)
            for low, high, rate in rates:
                if low <= x <= high:
                    return rate

        inputs = localdict['inputs']
        if 'ANNUAL_TAXABLE' not in inputs:
            return 0
        annual_taxable = inputs['ANNUAL_TAXABLE'].amount

        # Note: Exoneration for children in charge is managed on the salary.rule for the amount
        rates = self._rule_parameter('holiday_pay_pp_rates')
        pp_rate = find_rates(annual_taxable, rates)

        # Rate Reduction for children in charge
        children = self.employee_id.dependent_children
        children_reduction = self._rule_parameter('holiday_pay_pp_rate_reduction')
        if children and annual_taxable <= children_reduction.get(children, children_reduction[5])[1]:
            pp_rate *= (1 - children_reduction.get(children, children_reduction[5])[0] / 100.0)
        return pp_rate

    def _get_be_withholding_taxes(self, localdict):
        self.ensure_one()

        categories = localdict['categories']

        def compute_basic_bareme(value):
            rates = self._rule_parameter('basic_bareme_rates')
            rates = [(limit or float('inf'), rate) for limit, rate in rates]  # float('inf') because limit equals None for last level
            rates = sorted(rates)

            basic_bareme = 0
            previous_limit = 0
            for limit, rate in rates:
                basic_bareme += max(min(value, limit) - previous_limit, 0) * rate
                previous_limit = limit
            return float_round(basic_bareme, precision_rounding=0.01)

        def convert_to_month(value):
            return float_round(value / 12.0, precision_rounding=0.01, rounding_method='DOWN')

        version = self.version_id
        # PART 1: Withholding tax amount computation
        withholding_tax_amount = 0.0

        taxable_amount = categories['GROSS']  # Base imposable

        if self.date_from.year < 2023:
            lower_bound = taxable_amount - taxable_amount % 15
        else:
            lower_bound = taxable_amount

        # yearly_gross_revenue = Revenu Annuel Brut
        yearly_gross_revenue = lower_bound * 12.0

        # yearly_net_taxable_amount = Revenu Annuel Net Imposable
        if yearly_gross_revenue <= self._rule_parameter('yearly_gross_revenue_bound_expense'):
            yearly_net_taxable_revenue = yearly_gross_revenue * (1.0 - 0.3)
        else:
            yearly_net_taxable_revenue = yearly_gross_revenue - self._rule_parameter('expense_deduction')

        # BAREME III: Non resident
        if version.is_non_resident:
            basic_bareme = compute_basic_bareme(yearly_net_taxable_revenue)
            withholding_tax_amount = convert_to_month(basic_bareme)
        else:
            # BAREME I: Isolated or spouse with income
            if version.marital in ['divorced', 'single', 'widower'] or (version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status != 'without_income'):
                basic_bareme = max(compute_basic_bareme(yearly_net_taxable_revenue) - self._rule_parameter('deduct_single_with_income'), 0.0)
                withholding_tax_amount = convert_to_month(basic_bareme)

            # BAREME II: spouse without income
            if version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status == 'without_income':
                yearly_net_taxable_revenue_for_spouse = min(yearly_net_taxable_revenue * 0.3, self._rule_parameter('max_spouse_income'))
                basic_bareme_1 = compute_basic_bareme(yearly_net_taxable_revenue_for_spouse)
                basic_bareme_2 = compute_basic_bareme(yearly_net_taxable_revenue - yearly_net_taxable_revenue_for_spouse)
                withholding_tax_amount = convert_to_month(max(basic_bareme_1 + basic_bareme_2 - 2 * self._rule_parameter('deduct_single_with_income'), 0))

        # Reduction for other family charges
        if (version.children and version.dependent_children) or (version.other_dependent_people and (version.dependent_seniors or version.dependent_juniors)):
            if version.marital in ['divorced', 'single', 'widower'] or (version.spouse_fiscal_status != 'without_income'):

                # if version.marital in ['divorced', 'single', 'widower']:
                #     withholding_tax_amount -= self._rule_parameter('isolated_deduction')
                if version.marital in ['divorced', 'single', 'widower'] and version.dependent_children:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction')
                if version.disabled:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction')
                if version.other_dependent_people and version.dependent_seniors:
                    withholding_tax_amount -= self._rule_parameter('dependent_senior_deduction') * version.dependent_seniors
                if version.other_dependent_people and version.dependent_juniors:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction') * version.dependent_juniors
                if version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status == 'low_income':
                    withholding_tax_amount -= self._rule_parameter('spouse_low_income_deduction')
                if version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status == 'low_pension':
                    withholding_tax_amount -= self._rule_parameter('spouse_other_income_deduction')
            if version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status == 'without_income':
                if version.disabled:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction')
                if version.disabled_spouse_bool:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction')
                if version.other_dependent_people and version.dependent_seniors:
                    withholding_tax_amount -= self._rule_parameter('dependent_senior_deduction') * version.dependent_seniors
                if version.other_dependent_people and version.dependent_juniors:
                    withholding_tax_amount -= self._rule_parameter('disabled_dependent_deduction') * version.dependent_juniors

        # Child Allowances
        n_children = version.dependent_children
        if n_children > 0:
            children_deduction = self._rule_parameter('dependent_basic_children_deduction')
            if n_children <= 8:
                withholding_tax_amount -= children_deduction.get(n_children, 0.0)
            if n_children > 8:
                withholding_tax_amount -= children_deduction.get(8, 0.0) + (n_children - 8) * self._rule_parameter('dependent_children_deduction')

        return - max(withholding_tax_amount, 0.0)

    def _get_be_special_social_cotisations(self, localdict):
        self.ensure_one()

        def find_rate(x, rates):
            for low, high, rate, basis, min_amount, max_amount in rates:
                if low <= x <= high:
                    return low, high, rate, basis, min_amount, max_amount
            return 0, 0, 0, 0, 0, 0

        categories = localdict['categories']
        version = self.version_id
        employee = version.employee_id
        wage = categories['BASIC']
        if not wage or version.is_non_resident:
            return 0.0

        if version.marital in ['divorced', 'single', 'widower'] or (version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status == 'without_income'):
            rates = self._rule_parameter('cp200_monss_isolated')
            if not rates:
                rates = [
                    (0.00, 1945.38, 0.00, 0.00, 0.00, 0.00),
                    (1945.39, 2190.18, 0.076, 0.00, 0.00, 18.60),
                    (2190.19, 6038.82, 0.011, 18.60, 0.00, 60.94),
                    (6038.83, 999999999.00, 1.000, 60.94, 0.00, 60.94),
                ]
            low, dummy, rate, basis, min_amount, max_amount = find_rate(wage, rates)
            return -min(max(basis + (wage - low + 0.01) * rate, min_amount), max_amount)

        if version.marital in ['married', 'cohabitant'] and version.spouse_fiscal_status != 'without_income':
            rates = self._rule_parameter('cp200_monss_couple')
            if not rates:
                rates = [
                    (0.00, 1095.09, 0.00, 0.00, 0.00, 0.00),
                    (1095.10, 1945.38, 0.00, 9.30, 9.30, 9.30),
                    (1945.39, 2190.18, 0.076, 0.00, 9.30, 18.60),
                    (2190.19, 6038.82, 0.011, 18.60, 0.00, 51.64),
                    (6038.83, 999999999.00, 1.000, 51.64, 51.64, 51.64),
                ]
            low, dummy, rate, basis, min_amount, max_amount = find_rate(wage, rates)
            if isinstance(max_amount, tuple):
                if version.spouse_fiscal_status in ['high_income', 'low_income']:
                    # conjoint avec revenus professionnels
                    max_amount = max_amount[0]
                else:
                    # conjoint sans revenus professionnels
                    max_amount = max_amount[1]
            return -min(max(basis + (wage - low + 0.01) * rate, min_amount), max_amount)
        return 0.0

    def _get_be_ip(self, localdict):
        self.ensure_one()
        contract = self.version_id
        if not contract.ip:
            return 0.0
        return self._get_paid_amount() * contract.ip_wage_rate / 100.0

    def _get_be_ip_deduction(self, localdict):
        self.ensure_one()
        tax_rate = 0.15
        ip_amount = self._get_be_ip(localdict)
        if not ip_amount:
            return 0.0
        ip_deduction_bracket_1 = self._rule_parameter('ip_deduction_bracket_1')
        ip_deduction_bracket_2 = self._rule_parameter('ip_deduction_bracket_2')
        if 0.0 <= ip_amount <= ip_deduction_bracket_1:
            tax_rate = tax_rate / 2.0
        elif ip_deduction_bracket_1 < ip_amount <= ip_deduction_bracket_2:
            tax_rate = tax_rate * 3.0 / 4.0
        return - min(ip_amount * tax_rate, 11745)

    def _get_employment_bonus_employees_volet_A(self, localdict):
        categories = localdict['categories']
        result_rules = localdict['result_rules']
        if not self.worked_days_line_ids and not self.env.context.get('salary_simulation'):
            return 0

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        if self.env.context.get('salary_simulation'):
            paid_hours = 1
            total_hours = 1
        else:
            worked_days = self.worked_days_line_ids.filtered(lambda wd: wd.code not in ['LEAVE300', 'LEAVE301', 'MEDIC01'])
            paid_hours = sum(worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours'))  # H
            total_hours = sum(worked_days.mapped('number_of_hours'))  # U

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = categories['BRUT'] - result_rules['HolPayRecN']['total'] - result_rules['HolPayRecN1']['total']
        salary = basic * total_hours / paid_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        bonus_basic_amount_volet_A = self._rule_parameter('work_bonus_basic_amount_volet_A')
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        wage_middle_bound = self._rule_parameter('l10n_be_work_bonus_reference_wage_middle')
        wage_higher_bound = self._rule_parameter('work_bonus_reference_wage_high')
        if salary <= wage_lower_bound:
            result = bonus_basic_amount_volet_A
        elif salary <= wage_middle_bound:
            result = bonus_basic_amount_volet_A
        elif salary <= wage_higher_bound:
            coeff = self._rule_parameter('work_bonus_coeff')
            result = bonus_basic_amount_volet_A - (coeff * (salary - wage_middle_bound))
        else:
            result = 0

        # 3. - Détermination du montant de la réduction (P)
        result = result * paid_hours / total_hours  # P = (H/U) x R

        return result

    def _get_employment_bonus_employees_volet_B(self, localdict):
        categories = localdict['categories']
        result_rules = localdict['result_rules']
        if not self.worked_days_line_ids and not self.env.context.get('salary_simulation'):
            return 0

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        if self.env.context.get('salary_simulation'):
            paid_hours = 1
            total_hours = 1
        else:
            worked_days = self.worked_days_line_ids.filtered(lambda wd: wd.code not in ['LEAVE300', 'LEAVE301', 'MEDIC01'])
            paid_hours = sum(worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours'))  # H
            total_hours = sum(worked_days.mapped('number_of_hours'))  # U

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = categories['BRUT'] - result_rules['HolPayRecN']['total'] - result_rules['HolPayRecN1']['total']
        salary = basic * total_hours / paid_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        bonus_basic_amount = self._rule_parameter('work_bonus_basic_amount')
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        wage_middle_bound = self._rule_parameter('l10n_be_work_bonus_reference_wage_middle')
        wage_higher_bound = self._rule_parameter('work_bonus_reference_wage_high')
        if salary <= wage_lower_bound:
            result = bonus_basic_amount
        elif salary <= wage_middle_bound:
            coeff = self._rule_parameter('l10n_be_work_bonus_coeff_low')
            result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
        elif salary <= wage_higher_bound:
            result = 0
        else:
            result = 0

        # 3. - Détermination du montant de la réduction (P)
        result = result * paid_hours / total_hours  # P = (H/U) x R

        return result

    # ref: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/deductions/workers_reductions/workbonus.html
    def _get_employment_bonus_employees(self, localdict):
        self.ensure_one()
        categories = localdict['categories']
        result_rules = localdict['result_rules']
        if self.date_from >= date(2024, 4, 1):
            bonus_volet_A = localdict['result_rules']['EmpBonus.A']['total']
            bonus_volet_B = localdict['result_rules']['EmpBonus.B']['total']
            result = bonus_volet_A + bonus_volet_B
            return min(result, -categories['ONSS'])

        bonus_basic_amount = self._rule_parameter('work_bonus_basic_amount')
        wage_lower_bound = self._rule_parameter('work_bonus_reference_wage_low')
        if not self.worked_days_line_ids and not self.env.context.get('salary_simulation'):
            return 0

        # S = (W / H) * U
        # W = salaire brut
        # H = le nombre d'heures de travail déclarées avec un code prestations 1, 3, 4, 5 et 20;
        # U = le nombre maximum d'heures de prestations pour le mois concerné dans le régime de travail concerné
        if self.env.context.get('salary_simulation'):
            paid_hours = 1
            total_hours = 1
        else:
            worked_days = self.worked_days_line_ids.filtered(lambda wd: wd.code not in ['LEAVE300', 'LEAVE301', 'MEDIC01'])
            paid_hours = sum(worked_days.filtered(lambda wd: wd.amount).mapped('number_of_hours'))  # H
            total_hours = sum(worked_days.mapped('number_of_hours'))  # U

        # 1. - Détermination du salaire mensuel de référence (S)
        basic = categories['BRUT'] - result_rules['HolPayRecN']['total'] - result_rules['HolPayRecN1']['total']
        salary = basic * total_hours / paid_hours  # S = (W/H) x U

        # 2. - Détermination du montant de base de la réduction (R)
        if self.date_from < date(2023, 7, 1):
            if salary <= wage_lower_bound:
                result = bonus_basic_amount
            elif salary <= self._rule_parameter('work_bonus_reference_wage_high'):
                coeff = self._rule_parameter('work_bonus_coeff')
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            else:
                result = 0
        else:
            if salary <= wage_lower_bound:
                result = bonus_basic_amount
            elif salary <= self._rule_parameter('l10n_be_work_bonus_reference_wage_middle'):
                coeff = self._rule_parameter('l10n_be_work_bonus_coeff_low')
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            elif salary <= self._rule_parameter('work_bonus_reference_wage_high'):
                coeff = self._rule_parameter('work_bonus_coeff')
                result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
            else:
                result = 0

        # 3. - Détermination du montant de la réduction (P)
        result = result * paid_hours / total_hours  # P = (H/U) x R

        return min(result, -categories['ONSS'])

    def _get_withholding_taxes_after_child_allowances(self, rates, gross, apply_reduction=True):

        def find_rates(x, rates):
            low_bound, high_bound = rates[0][0], rates[-1][1]
            x = min(max(low_bound, x), high_bound)
            for low, high, rate in rates:
                if low <= x <= high:
                    return rate / 100.0

        children_exoneration = self._rule_parameter('holiday_pay_pp_exoneration')
        children_reduction = self._rule_parameter('holiday_pay_pp_rate_reduction')

        version = self.version_id

        monthly_revenue = version._get_contract_wage()
        # Count ANT in yearly remuneration
        if version.internet:
            monthly_revenue += 5.0
        if version.mobile and not version.internet:
            monthly_revenue += 4.0 + 5.0
        if version.mobile and version.internet:
            monthly_revenue += 4.0
        if version.has_laptop:
            monthly_revenue += 7.0

        yearly_revenue = monthly_revenue * (1 - 0.1307) * 12.0

        if version.transport_mode_car:
            if 'vehicle_id' in self:
                yearly_revenue += self.vehicle_id._get_car_atn(date=self.date_from) * 12.0
            else:
                yearly_revenue += version.car_atn * 12.0

        # Exoneration
        children = version.dependent_children
        if children > 0 and yearly_revenue <= children_exoneration.get(children, children_exoneration[12]):
            yearly_revenue -= children_exoneration.get(children, children_exoneration[12]) - yearly_revenue
            yearly_revenue = max(yearly_revenue, 0)

        withholding_tax_amount = gross * find_rates(yearly_revenue, rates)
        # Reduction
        if (apply_reduction and
            children > 0 and
            yearly_revenue <= children_reduction.get(children, children_reduction[5])[1]
        ):
            withholding_tax_amount *= (1 - children_reduction.get(children, children_reduction[5])[0] / 100.0)

        return - withholding_tax_amount

    def _get_be_double_holiday_withholding_taxes(self, localdict):
        self.ensure_one()
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument

        rates = self._rule_parameter('holiday_pay_pp_rates')

        categories = localdict['categories']
        if self.struct_id.code == "CP200DOUBLE":
            gross = categories['GROSS']
        elif self.struct_id.code == "CP200MONTHLY":
            gross = categories['DDPG']

        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _get_thirteen_month_withholding_taxes(self, localdict):
        self.ensure_one()
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument

        rates = self._rule_parameter('exceptional_allowances_pp_rates')
        categories = localdict['categories']
        gross = categories['GROSS']

        return self._get_withholding_taxes_after_child_allowances(rates, gross)

    def _get_termination_fees_withholding_taxes(self, localdict):
        # See: https://www.securex.eu/lex-go.nsf/vwReferencesByCategory_fr/52DA120D5DCDAE78C12584E000721081?OpenDocument
        if self.date_from.year >= 2024:
            self.ensure_one()

            rates = self._rule_parameter('termination_fees_pp_rates')
            categories = localdict['categories']
            gross = categories['GROSS']

            return self._get_withholding_taxes_after_child_allowances(rates, gross, apply_reduction=False)

        else:
            return self._get_be_withholding_taxes(localdict)

    def _get_withholding_reduction(self, localdict):
        self.ensure_one()
        categories = localdict['categories']
        if categories['EmpBonus']:
            if self.date_from >= date(2024, 4, 1):
                bonus_volet_A = localdict['result_rules']['EmpBonus.A']['total']
                bonus_volet_B = localdict['result_rules']['EmpBonus.B']['total']
                reduction = bonus_volet_A * 0.3314 + bonus_volet_B * 0.5254
            else:
                reduction = categories['EmpBonus'] * 0.3314
            return min(abs(categories['PP']), reduction)
        return 0.0

    def _get_impulsion_plan_amount(self, localdict):
        self.ensure_one()
        start = self.employee_id.contract_date_start
        end = self.date_to
        number_of_months = (end.year - start.year) * 12 + (end.month - start.month)
        numerator = sum(wd.number_of_hours for wd in self.worked_days_line_ids if wd.amount > 0)
        denominator = 4 * self.version_id.resource_calendar_id.hours_per_week
        coefficient = numerator / denominator
        if self.version_id.l10n_be_impulsion_plan == '25yo':
            if 0 <= number_of_months <= 23:
                theorical_amount = 500.0
            elif 24 <= number_of_months <= 29:
                theorical_amount = 250.0
            elif 30 <= number_of_months <= 35:
                theorical_amount = 125.0
            else:
                theorical_amount = 0
            return min(theorical_amount, theorical_amount * coefficient)
        if self.version_id.l10n_be_impulsion_plan == '12mo':
            if 0 <= number_of_months <= 11:
                theorical_amount = 500.0
            elif 12 <= number_of_months <= 17:
                theorical_amount = 250.0
            elif 18 <= number_of_months <= 23:
                theorical_amount = 125.0
            else:
                theorical_amount = 0
            return min(theorical_amount, theorical_amount * coefficient)
        return 0

    def _get_onss_restructuring(self, localdict):
        self.ensure_one()
        # Source: https://www.onem.be/fr/documentation/feuille-info/t115

        # 1. Grant condition
        # A worker who has been made redundant following a restructuring benefits from a reduction in his personal contributions under certain conditions:
        # - The engagement must take place during the validity period of the reduction card. The reduction card is valid for 6 months, calculated from date to date, following the termination of the employment contract.
        # - The gross monthly reference salary does not exceed
        # o 3.071.90: if the worker is under 30 years of age at the time of entry into service
        # o 4,504.93: if the worker is at least 30 years old at the time of entry into service
        # 2. Amount of reduction
        # Lump sum reduction of € 133.33 per month (full time - full month) in personal social security contributions.
        # If the worker does not work full time for a full month or if he works part time, this amount is reduced proportionally.

        # So the reduction is:
        # 1. Full-time worker: P = (J / D) x 133.33
        # - Full time with full one month benefits: € 133.33

        # Example the worker entered service on 02/01/2021 and worked the whole month
        # - Full time with incomplete services: P = (J / D) x 133.33
        # Example: the worker entered service on February 15 -> (10/20) x 133.33 = € 66.665
        # P = amount of reduction
        # J = the number of worker's days declared with a benefit code 1, 3, 4, 5 and 20 .;
        # D = the maximum number of days of benefits for the month concerned in the work scheme concerned.

        # 2. Part-time worker: P = (H / U) x 133.33
        # Example: the worker starts 02/01/2021 and works 19 hours a week.
        # (76/152) x 133.33 = € 66.665
        # Example: the worker starts 02/15/2021 and works 19 hours a week.
        # (38/155) x 133.33 = 33.335 €

        # P = amount of reduction
        # H = the number of working hours declared with a service code 1, 3, 4, 5 and 20;
        # U = the number of monthly hours corresponding to D.

        # 3. Duration of this reduction
        # The benefit applies to all periods of occupation that fall within the period that:
        # starts to run on the day you start your first occupation during the validity period of the restructuring reduction card;
        # and which ends on the last day of the second quarter following the start date of this first occupation.
        # 4. Formalities to be completed
        # The employer deducts the lump sum from the normal amount of personal contributions when paying the remuneration.
        # The ONEM communicates to the ONSS the data concerning the identification of the worker and the validity date of the card.

        # 5. Point of attention
        # If the worker also benefits from a reduction in his personal contributions for low wages, the cumulation between this reduction and that for restructuring cannot exceed the total amount of personal contributions due.

        # If this is the case, we must first reduce the restructuring reduction.

        # Example:
        # - personal contributions = 200 €
        # - restructuring reduction = € 133.33
        # - low salary reduction = 100 €

        # The total amount of reductions exceeds the contributions due. We must therefore first reduce the restructuring reduction and then the balance of the low wage reduction.
        if not self.worked_days_line_ids:
            return 0

        employee = self.version_id.employee_id
        contract_date_start = employee.contract_date_start
        birthdate = employee.birthday
        age = relativedelta(contract_date_start, birthdate).years
        if age < 30:
            threshold = self._rule_parameter('onss_restructuring_before_30')
        else:
            threshold = self._rule_parameter('onss_restructuring_after_30')

        salary = self.paid_amount
        if salary > threshold:
            return 0

        amount = self._rule_parameter('onss_restructuring_amount')

        paid_hours = sum(self.worked_days_line_ids.filtered(lambda wd: wd.amount).mapped('number_of_hours'))
        total_hours = sum(self.worked_days_line_ids.mapped('number_of_hours'))
        ratio = paid_hours / total_hours if total_hours else 0

        start = contract_date_start
        end = self.date_to
        number_of_months = (end.year - start.year) * 12 + (end.month - start.month)
        if 0 <= number_of_months <= 6:
            return amount * ratio
        return 0

    def _get_representation_fees_threshold(self, localdict):
        return self._rule_parameter('cp200_representation_fees_threshold')

    def _get_representation_fees(self, localdict):
        self.ensure_one()
        categories = localdict['categories']
        worked_days = localdict['worked_days']
        # Representation fees aren't paid if there's no basic pay or no time worked
        if categories['BASIC'] and (
            not all(day.work_entry_type_id.is_leave for day in worked_days.values())
            or self.env.context.get('salary_simulation')
        ):
            version = self.version_id
            calendar = version.resource_calendar_id
            days_per_week = calendar._get_days_per_week()
            work_time_rate = version.resource_calendar_id.work_time_rate

            threshold = 0 if ('OUT' in worked_days and worked_days['OUT'].number_of_hours) else self._get_representation_fees_threshold(localdict)
            if days_per_week and self.env.context.get('salary_simulation_full_time'):
                result = version.representation_fees
            elif days_per_week and version.representation_fees > threshold:
                # Only part of the representation costs are pro-rated because certain costs are fully
                # covered for the company (teleworking costs, mobile phone, internet, etc., namely (for 2021):
                # - 144.31 € (Tax, since 2021 - coronavirus)
                # - 30 € (internet)
                # - 25 € (phone)
                # - 80 € (car management fees)
                # = Total € 279.31
                # Legally, they are not prorated according to the occupancy fraction.
                # In summary, those who select amounts of for example 150 € and 250 €, have nothing pro-rated
                # because the amounts are covered in an irreducible way.
                # For those who have selected the maximum of 399 €, there is therefore only the share of
                # +-120 € of representation expenses which is then subject to prorating.

                # Credit time, but with only half days (otherwise it's taken into account)
                is_credit_time_only_half_days = version.l10n_be_time_credit and work_time_rate and \
                    work_time_rate < 100 and (days_per_week == 5 or not self.representation_fees_missing_days)
                # Contractual part time
                is_contractual_part_time = not version.l10n_be_time_credit and work_time_rate < 100
                if is_credit_time_only_half_days or is_contractual_part_time:
                    total_amount = threshold + (version.representation_fees - threshold) * work_time_rate / 100
                else:
                    total_amount = version.representation_fees

                if total_amount > threshold:
                    daily_amount = (total_amount - threshold) * 3 / 13 / days_per_week
                    result = max(0, total_amount - daily_amount * self.representation_fees_missing_days)
            elif days_per_week:
                result = version.representation_fees
            else:
                result = 0
        else:
            result = 0
        return float_round(result, precision_digits=2)

    def _get_serious_representation_fees(self, localdict):
        self.ensure_one()
        return min(self._get_representation_fees(localdict), self._get_representation_fees_threshold(localdict))

    def _get_volatile_representation_fees(self, localdict):
        self.ensure_one()
        return max(self._get_representation_fees(localdict) - self._get_representation_fees_threshold(localdict), 0)

    def _get_holiday_pay_recovery(self, localdict, recovery_type):
        """
            See: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/intermediates#intermediate_row_196b32c7-9d98-4233-805d-ca9bf123ff48

            When an employee changes employer, he receives the termination pay and a vacation certificate
            stating his vacation rights. When he subsequently takes vacation with his new employer, the latter
            must, when paying the simple vacation pay, take into account the termination pay that the former
            employer has already paid.

            From an exchange of letters with the SPF ETCS and the Inspectorate responsible for the control of
            social laws, it turned out that when calculating the simple vacation pay, the new employer must
            deduct the exit pay based on the number of vacation days taken. The rule in the ONSS instructions
            according to which the new employer must take into account the exit vacation pay only once when the
            employee takes his main vacation is abolished.

            When the salary of an employee with his new employer is higher than the salary he had with his
            previous employer, his new employer will have, each time he takes vacation days, to make a
            calculation to supplement the nest egg. exit from these days up to the amount of the simple vacation
            pay to which the worker is entitled.

            Concretely:

            2020 vacation certificate (full year):
            - simple allowance 1,917.50 EUR
                - this amounts to 1917.50 / 20 EUR = 95.875 EUR per day of vacation
                - holidays 2021, for example when taking 5 days in April 2021
            - monthly salary with the new employer: 3000.00 EUR / month
                - simple nest egg:
                     - remuneration code 12: 5/20 x 1917.50 = 479.38 EUR
                     - remuneration code 1: (5/22 x 3000.00) - 479.38 = 202.44 EUR
                - ordinary days for the month of April:
                    - remuneration code 1: 17/22 x 3000.00 = 2318.18 EUR
                    - The examples included in the ONSS instructions will be adapted in the next publication.
        """
        self.ensure_one()
        worked_days = localdict['worked_days']
        if 'LEAVE120' not in worked_days or not worked_days['LEAVE120'].amount:
            return 0
        employee = self.employee_id
        number_of_days = employee['l10n_be_holiday_pay_number_of_days_' + recovery_type]
        all_payslips_during_civil_year = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', date(self.date_from.year, 1, 1)),
            ('date_to', '<=', date(self.date_from.year, 12, 31)),
            ('state', 'in', ['validated', 'paid']),
        ])
        paid_leave_days = all_payslips_during_civil_year._get_worked_days_line_values(['LEAVE120'], ['number_of_days'], True)['LEAVE120']['sum']['number_of_days']
        remaining_day = number_of_days - paid_leave_days
        if remaining_day <= 0:
            return 0
        if self.wage_type == 'hourly':
            employee_hourly_cost = self.version_id.hourly_wage
        else:
            if self.date_from.year < 2024:
                employee_hourly_cost = self.version_id.contract_wage / self.sum_worked_hours
            else:
                employee_hourly_cost = self.version_id.contract_wage * 3 / 13 / self.version_id.resource_calendar_id.hours_per_week
        remaining_day_amount = min(remaining_day, number_of_days) * employee_hourly_cost * 7.6
        days_to_recover = employee['l10n_be_holiday_pay_to_recover_' + recovery_type]
        max_amount_to_recover = min(days_to_recover, employee_hourly_cost * number_of_days * 7.6)
        paid_leave_data = self._get_worked_days_line_values(['LEAVE120'], ['amount', 'number_of_hours'], True)['LEAVE120']['sum']
        holiday_amount = min(paid_leave_data['amount'], employee_hourly_cost * paid_leave_data['number_of_hours'])
        remaining_amount = max(0, max_amount_to_recover - employee['l10n_be_holiday_pay_recovered_' + recovery_type])
        return - min(remaining_amount, remaining_day_amount, holiday_amount)

    def _get_holiday_pay_recovery_n(self, localdict):
        return self._get_holiday_pay_recovery(localdict, 'n')

    def _get_holiday_pay_recovery_n1(self, localdict):
        return self._get_holiday_pay_recovery(localdict, 'n1')

    def _get_termination_n_basic_double(self, localdict):
        self.ensure_one()
        inputs = localdict['inputs']
        result_qty = 1
        result_rate = 6.8
        result = inputs['GROSS_REF'].amount if 'GROSS_REF' in inputs else 0
        result_name = inputs['GROSS_REF'].name if 'GROSS_REF' in inputs else None
        date_from = self.date_from
        if self.struct_id.code == "CP200HOLN1":
            existing_double_pay = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['validated', 'paid']),
                ('struct_id', '=', self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id),
                ('date_from', '>=', date(date_from.year, 1, 1)),
                ('date_to', '<=', date(date_from.year, 12, 31)),
            ])
            if existing_double_pay:
                result = 0
        return (result_qty, result_rate, result, result_name)
