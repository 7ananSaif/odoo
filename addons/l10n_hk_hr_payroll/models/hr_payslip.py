# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import re
from collections import defaultdict
from datetime import datetime, date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.float_utils import float_compare


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    l10n_hk_worked_days_leaves_count = fields.Integer(
        string='Worked Days Leaves Count',
        compute='_compute_worked_days_leaves_count',
    )
    l10n_hk_713_gross = fields.Monetary(
        string='713 Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_mpf_gross = fields.Monetary(
        string='MPF Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_autopay_gross = fields.Monetary(
        string='AutoPay Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_second_batch_autopay_gross = fields.Monetary(
        string='Second Batch AutoPay Gross',
        compute='_compute_gross',
        store=True,
    )
    l10n_hk_average_daily_wage = fields.Monetary(
        string='Average Daily Wage',
        help='Calculated as per the Employment (Amendment) Ordinance 2007: (Total of fully paid wages earned in the 12-month period) / (Total number of fully paid days in that period).',
        compute='_compute_average_daily_wage',
    )
    l10n_hk_includes_eoy_pay = fields.Boolean(
        string='End-Of-Year Pay',
        compute='_compute_includes_eoy_pay',
        store=True,
        readonly=False,
    )
    l10n_hk_use_mpf_offsetting = fields.Boolean(
        string='Apply MPF Offsetting',
        compute='_compute_l10n_hk_use_mpf_offsetting',
        store=True,
        readonly=False,
    )

    @api.depends('worked_days_line_ids')
    def _compute_worked_days_leaves_count(self):
        for payslip in self:
            payslip.l10n_hk_worked_days_leaves_count = len(payslip.worked_days_line_ids.filtered(lambda wd: wd.l10n_hk_leave_id))

    @api.depends('line_ids.total', 'struct_id')
    def _compute_gross(self):
        """
        Compute gross amounts at the time of this payslip.
        They will be made available in the Payroll Analysis report.
        """
        related_struct = self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary', raise_if_not_found=False)
        if not related_struct:
            return

        hk_slip = self.filtered(lambda s: s.struct_id == related_struct)
        line_values = hk_slip._get_line_values(['713_GROSS', 'MPF_GROSS', 'MEA', 'SBA'])
        for payslip in hk_slip:
            payslip.l10n_hk_713_gross = line_values['713_GROSS'][payslip.id]['total']
            payslip.l10n_hk_mpf_gross = line_values['MPF_GROSS'][payslip.id]['total']
            payslip.l10n_hk_autopay_gross = line_values['MEA'][payslip.id]['total']
            payslip.l10n_hk_second_batch_autopay_gross = line_values['SBA'][payslip.id]['total']

    @api.depends('input_line_ids')
    def _compute_average_daily_wage(self):
        """
        Calculate and return the Average Daily Wage (ADW), which is used to calculate payments for various statutory entitlements, including:
        - Holiday Pay
        - Annual Leave Pay
        - Sickness Allowance
        - Maternity and Paternity Leave Pay
        - Payment in lieu of notice

        The calculation is governed by the Employment (Amendment) Ordinance 2007:
            ADW = (Total wages earned in the 12-month period) / (Total number of days in that period)

        In order to be fair to the employee, the total wage calculation must exclude days for which the employee was not
        paid their full pay (sick leave,...) as well as the wages of these days.

        The period in which to look for the ADW is based on the last 365 days, and not the last 12 months.

        Example:
            Natalie Chan takes an annual leave from August 4, 2025, to August 6, 2025.
            The wages she received in the last 12 months are of HK350,000.
            During this period,she took 5 days of unpaid leave and 2 days of sickness leave (for which she was paid a total of HK1,500).

            The calculation should then be:
            - Disregard the days of leave not fully paid from the total calendar days.
            - Disregard the payments made for those specific leave days from the total wages.

            So the ADW is: (HK$350,000-HK$1,500) / (365 - 5 - 2) = HK$973.46
        :return: The ADW for the period.
        """
        for slip in self:
            if slip.country_code != 'HK':
                slip.l10n_hk_average_daily_wage = 0
                continue

            adw = 0
            average_daily_wage = sum(slip.input_line_ids.filtered(lambda line: line.code == 'AVERAGE_DAILY_WAGE').mapped('amount'))
            if average_daily_wage:
                slip.l10n_hk_average_daily_wage = average_daily_wage
                continue

            last_year_payslips = slip._get_previous_year_payslips(order='date_from')
            if last_year_payslips:
                gross = last_year_payslips._get_line_values(['713_GROSS'], compute_sum=True)['713_GROSS']['sum']['total']
                gross -= last_year_payslips._get_total_non_full_pay()
                number_of_days = last_year_payslips._get_number_of_worked_days(only_full_pay=True)
                if number_of_days > 0:
                    adw = gross / number_of_days

            slip.l10n_hk_average_daily_wage = adw

    @api.depends('date_to', 'company_id')
    def _compute_includes_eoy_pay(self):
        for slip in self.filtered(lambda s: s.country_code == 'HK'):
            if not slip.company_id.l10n_hk_eoy_pay_month:
                slip.l10n_hk_includes_eoy_pay = False

            last_year_payslips = slip._get_previous_year_payslips(order='date_from desc')
            slip.l10n_hk_includes_eoy_pay = str(slip.date_to.month) == slip.company_id.l10n_hk_eoy_pay_month and last_year_payslips

    @api.depends('company_id')
    def _compute_l10n_hk_use_mpf_offsetting(self):
        for slip in self.filtered(lambda s: s.country_code == 'HK'):
            slip.l10n_hk_use_mpf_offsetting = slip.company_id.l10n_hk_use_mpf_offsetting

    def _get_paid_amount(self):
        """
        When the paid amount is very slightly off from the wage, we assume that it is due to a rounding
        error and return the wage amount instead of the computed value.
        """
        self.ensure_one()
        res = super()._get_paid_amount()
        if self.struct_id.country_id.code == 'HK':
            if float_compare(res, self._get_contract_wage(), precision_rounding=0.1) == 0:
                return self._get_contract_wage()
        return res

    def _get_previous_year_payslips(self, order=None):
        """
        Returns all payslips from the previous year, for the same struc and employee as the one being used in the payslip in
        self.
        :param order: Optional order that can be used instead of the default one when searching for the payslips.
        :return: The recordset of matching payslips from the previous year.
        """
        self.ensure_one()
        return self.env['hr.payslip'].search([
            ("state", "in", ["paid", "validated"]),
            ("date_from", ">=", self.date_from + relativedelta(months=-12, day=1)),
            ("date_to", "<", self.date_to + relativedelta(day=1)),
            ("struct_id", "=", self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id),
            ("employee_id", "=", self.employee_id.id),
        ], order=order)

    def _get_number_of_non_full_pay_days(self):
        """
        Calculates the amount of days for which the employee was not paid their full wage.
        This is important information when calculating the Average Daily Wage (ADW).
        :return: Amount of non-full pay days.
        """
        wds = self.worked_days_line_ids.filtered(lambda wd: wd.work_entry_type_id.amount_rate < 1)
        return sum([wd.number_of_days for wd in wds])

    def _get_number_of_worked_days(self, only_full_pay=False):
        """
        Calculates the amount of days during which the employee worked.
        :param only_full_pay: Optionally, filter out days were the pay was not their full wage.
        :return: Amount of worked days.
        """
        wds = self.worked_days_line_ids.filtered(lambda wd: wd.code not in ['LEAVE90', 'OUT'])
        number_of_days = sum([wd.number_of_days for wd in wds])
        if only_full_pay:
            return number_of_days - self._get_number_of_non_full_pay_days()
        return number_of_days

    def _get_credit_time_lines(self):
        if self.struct_id.country_id.code != 'HK':
            return super()._get_credit_time_lines()
        return []

    def _get_worked_day_lines_values(self, domain=None):
        """
        Calculate the values that should be used to calculate the worked days lines of the payslip.
        Adds support for leave starting before the payslip period.
        :param domain: An optional domain used to filter work entries.
        :return: The worked days lines values.
        """
        self.ensure_one()
        res = super()._get_worked_day_lines_values(domain)
        if self.struct_id.country_id.code != 'HK':
            return res

        domain = Domain(domain or Domain.TRUE)
        current_month_domain = domain & (
            Domain('leave_id', '=', False)
            | Domain('leave_id.date_from', '>=', self.date_from)
        )
        res = super()._get_worked_day_lines_values(current_month_domain)

        hours_per_day = self._get_worked_day_lines_hours_per_day()
        date_from = datetime.combine(self.date_from, datetime.min.time())
        date_to = datetime.combine(self.date_to, datetime.max.time())
        remaining_work_entries_domain = domain & Domain('leave_id.date_from', '<', self.date_from)
        work_entries_dict = self.env['hr.work.entry']._read_group(
            self.version_id._get_work_hours_domain(date_from, date_to, domain=remaining_work_entries_domain),
            ['leave_id', 'work_entry_type_id'],
            ['duration:sum'],
        )
        work_entries = defaultdict(tuple)
        work_entries.update({
            (work_entry_type.id, leave.id): hours
            for leave, work_entry_type, hours in work_entries_dict
        })
        for work_entry, hours in work_entries.items():
            work_entry_id, leave_id = work_entry
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            day_rounded = self._round_days(work_entry_type, days)
            res.append({
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_id,
                'number_of_days': day_rounded,
                'number_of_hours': hours,
                'l10n_hk_leave_id': leave_id,
            })
        return res

    def _get_worked_day_lines(self, domain=None, check_out_of_version=True):
        """
        Calculate worked days values to apply on the payslip.
        If the employee is out of contract during a part of the period, a out of contract line will be added to fill the
        gap.
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        self.ensure_one()
        domain = Domain(domain or Domain.TRUE)
        res = super()._get_worked_day_lines(domain, check_out_of_version)
        if self.struct_id.country_id.code != 'HK':
            return res

        contract = self.version_id
        if contract.resource_calendar_id:
            if not check_out_of_version:
                return res
            out_days, out_hours = 0, 0
            reference_calendar = self._get_out_of_contract_calendar()
            domain &= Domain('work_entry_type_id.is_leave', '=', True)
            if self.date_from < contract.date_start:
                start = fields.Datetime.to_datetime(self.date_from)
                stop = fields.Datetime.to_datetime(contract.date_start) + relativedelta(days=-1, hour=23, minute=59)
                out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                out_days += out_time['days']
                out_hours += out_time['hours']
            if contract.date_end and contract.date_end < self.date_to:
                start = fields.Datetime.to_datetime(contract.date_end) + relativedelta(days=1)
                stop = fields.Datetime.to_datetime(self.date_to) + relativedelta(hour=23, minute=59)
                out_time = reference_calendar.get_work_duration_data(start, stop, compute_leaves=False, domain=domain)
                out_days += out_time['days']
                out_hours += out_time['hours']
            work_entry_type = self.env.ref('hr_work_entry.hr_work_entry_type_out_of_contract', raise_if_not_found=False)
            if work_entry_type and (out_days or out_hours):
                existing = False
                for worked_days in res:
                    if worked_days['work_entry_type_id'] == work_entry_type.id:
                        worked_days['number_of_days'] += out_days
                        worked_days['number_of_hours'] += out_hours
                        existing = True
                        break
                if not existing:
                    res.append({
                        'sequence': work_entry_type.sequence,
                        'work_entry_type_id': work_entry_type.id,
                        'number_of_days': out_days,
                        'number_of_hours': out_hours,
                    })
        return res

    def _get_total_non_full_pay(self):
        """ Calculate the total amount from all worked day lines concerning non-fully paid work entries. """
        total = 0
        for wd_line in self.worked_days_line_ids:
            if wd_line.work_entry_type_id.amount_rate == 1:
                continue
            total += wd_line.amount
        return total

    def _get_713_gross_at_date(self, request_date):
        """
        Helper returning the amount of the 713 gross at a specified date.
        The way it is done is by finding the last monthly payslip before that date, and getting the value from it.
        """
        employee_salary_struct = self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary')
        relevant_payslips = self.employee_id.slip_ids.filtered(
            lambda s: s.struct_id == employee_salary_struct and s.date_to < request_date
        )
        if relevant_payslips:
            latest_payslip = next(iter(relevant_payslips.sorted()))
            if not latest_payslip:
                return 0.0
            return latest_payslip._get_line_values(['713_GROSS'])['713_GROSS'][latest_payslip.id]['total']
        return 0.0

    def _get_years_of_services_per_period(self):
        """
        Calculate the years of services for the employee of the payslip, for both pre- and post-transition periods.

        :return: a tuple (pre_transition_yos, post_transition_yos)
        """
        self.ensure_one()
        contracts = self.employee_id.version_ids.sorted("contract_date_start", reverse=True)
        if not contracts:
            return 0, 0

        transition_date = date(2025, 5, 1)
        contract_end_date = contracts[0].date_end or self.date_to
        # Starts by calculating the pre-transition years of service.
        pre_transition_end_date = transition_date - relativedelta(days=1)  # April 30, 2025
        pre_transition_years = self.employee_id._get_years_of_service(self.employee_id._get_first_version_date(), pre_transition_end_date)

        # Continues by calculating the post-transition years of service.
        post_transition_start_date = transition_date
        post_transition_years = self.employee_id._get_years_of_service(max(self.employee_id._get_first_version_date(), post_transition_start_date), contract_end_date)

        return pre_transition_years, post_transition_years

    def _generate_h2h_autopay(self, header_data: dict) -> str:
        ctime = datetime.now()
        header = (
            f'H{header_data["digital_pic_id"]:<11}HKMFPS02{"":<3}'
            f'{header_data["customer_ref"]:<35}{ctime:%Y/%m/%d%H:%M:%S}'
            f'{"":<1}{header_data["authorisation_type"]}{"":<2}PH{"":<79}\n'
        )
        return header

    def _generate_hsbc_autopay(self, header_data: dict, payments_data: dict) -> str:
        acc_number = re.sub(r"[^0-9]", "", header_data['autopay_partner_bank_id'].acc_number)
        header = (
            f'PHF{header_data["payment_set_code"]}{header_data["ref"]:<12}{header_data["payment_date"]:%Y%m%d}'
            f'{acc_number + "SA" + header_data["currency"]:<35}'
            f'{header_data["currency"]}{header_data["payslips_count"]:07}{round(header_data["amount_total"] * 100):017}'
            f'{"":<1}{"":<311}\n'
        )
        datas = []
        for payment in payments_data:
            datas.append(
                f'PD{payment["bank_code"]:<3}{payment["type"].upper()}{payment["autopay_field"]:<34}'
                f'{round(payment["amount"] * 100):017}{payment["identifier"]:<35}{payment["ref"]:<35}'
                f'{payment["bank_account_name"]:<140}{"":<130}'
            )
        data = '\n'.join(datas)
        return header + data

    def _create_apc_file(self, payment_date, payment_set_code: str, batch_type: str = 'first', ref: str = None, file_name: str = None, **kwargs):
        invalid_payslips = self.filtered(lambda p: p.currency_id.name not in ['HKD', 'CNY'])
        if invalid_payslips:
            raise UserError(self.env._("Only accept HKD or CNY currency.\nInvalid currency for the following payslips:\n%s", '\n'.join(invalid_payslips.mapped('name'))))
        companies = self.mapped('company_id')
        if len(companies) > 1:
            raise UserError(self.env._("Only support generating the HSBC autopay report for one company."))
        currencies = self.mapped('currency_id')
        if len(currencies) > 1:
            raise UserError(self.env._("Only support generating the HSBC autopay report for one currency"))
        invalid_employees = self.mapped('employee_id').filtered(lambda e: not e.bank_account_ids)
        if invalid_employees:
            raise UserError(self.env._("Some employees (%s) don't have a bank account.", ','.join(invalid_employees.mapped('name'))))
        invalid_employees = self.mapped('employee_id').filtered(lambda e: not e.l10n_hk_autopay_account_type)
        if invalid_employees:
            raise UserError(self.env._("Some employees (%s) haven't set the autopay type.", ','.join(invalid_employees.mapped('name'))))
        invalid_banks = self.employee_id.bank_account_ids.mapped('bank_id').filtered(lambda b: not b.l10n_hk_bank_code)
        if invalid_banks:
            raise UserError(self.env._("Some banks (%s) don't have a bank code", ','.join(invalid_banks.mapped('name'))))
        # TODO: adapt for multiple bank accounts
        invalid_bank_accounts = self.mapped('employee_id').filtered(
            lambda e: e.l10n_hk_autopay_account_type in ['bban', 'hkid'] and not e.primary_bank_account_id.acc_holder_name)
        if invalid_bank_accounts:
            raise UserError(self.env._("Some bank accounts (%s) don't have a bank account name.", ','.join(invalid_bank_accounts.mapped('primary_bank_account_id.acc_number'))))
        rule_code = {'first': 'MEA', 'second': 'SBA'}[batch_type]
        payslips = self.filtered(lambda p: p.struct_id.code == 'CAP57MONTHLY' and p.line_ids.filtered(lambda line: line.code == rule_code))
        if not payslips:
            raise UserError(self.env._("No payslip to generate the HSBC autopay report."))

        autopay_type = self.company_id.l10n_hk_autopay_type
        if autopay_type == 'h2h':
            h2h_header_data = {
                'authorisation_type': kwargs.get('authorisation_type'),
                'customer_ref': kwargs.get('customer_ref', ''),
                'digital_pic_id': kwargs.get('digital_pic_id'),
                'payment_date': payment_date,
            }

        header_data = {
            'ref': ref,
            'currency': payslips.currency_id.name,
            'amount_total': sum(payslips.line_ids.filtered(lambda line: line.code == rule_code).mapped('amount')),
            'payment_date': payment_date,
            'payslips_count': len(payslips),
            'payment_set_code': payment_set_code,
            'autopay_partner_bank_id': payslips.company_id.l10n_hk_autopay_partner_bank_id,
        }

        payments_data = []
        for payslip in payslips:
            employee = payslip.employee_id
            bank_code = ''
            if employee.l10n_hk_autopay_account_type == 'bban':
                # The bank code is only expected when the autopay type is set to bban
                bank_code = employee.primary_bank_account_id.bank_id.l10n_hk_bank_code

            # The identifier used depends on the employee autopay type
            identifier = ''
            match employee.l10n_hk_autopay_account_type:
                case "bban":
                    identifier = re.sub(r"[^0-9]", "", employee.primary_bank_account_id.acc_number)
                case "svid":
                    identifier = employee.l10n_hk_autopay_svid
                case "emal":
                    identifier = employee.l10n_hk_autopay_email
                case "mobn":
                    identifier = employee.l10n_hk_autopay_mobile
                case "hkid":
                    identifier = employee.identification_id

            payments_data.append({
                'id': payslip.id,
                'ref': employee.l10n_hk_autopay_ref or '',
                'type': employee.l10n_hk_autopay_account_type,
                'amount': sum(payslip.line_ids.filtered(lambda line: line.code == rule_code).mapped('amount')),
                'identifier': re.sub(r'[^a-zA-Z0-9]', '', employee.identification_id or ''),
                'bank_code': bank_code,
                'autopay_field': identifier,
                'bank_account_name': employee.primary_bank_account_id.acc_holder_name or '',
            })

        apc_doc = payslips._generate_hsbc_autopay(header_data, payments_data)
        if autopay_type == 'h2h':
            apc_doc = payslips._generate_h2h_autopay(h2h_header_data) + apc_doc
        apc_binary = base64.encodebytes(apc_doc.encode('ascii'))

        file_name = file_name and file_name.replace('.apc', '')
        if batch_type == 'first':
            payslips.mapped('payslip_run_id').write({
                'l10n_hk_autopay_export_first_batch_date': payment_date,
                'l10n_hk_autopay_export_first_batch': apc_binary,
                'l10n_hk_autopay_export_first_batch_filename': (file_name or 'HSBC_Autopay_export_first_batch') + '.apc',
            })
        else:
            payslips.mapped('payslip_run_id').write({
                'l10n_hk_autopay_export_second_batch_date': payment_date,
                'l10n_hk_autopay_export_second_batch': apc_binary,
                'l10n_hk_autopay_export_second_batch_filename': (file_name or 'HSBC_Autopay_export_second_batch') + '.apc',
            })

    def write(self, vals):
        """ Force the payslip to recompute itself when adding payslip inputs. """
        res = super().write(vals)
        if 'input_line_ids' in vals:
            self.filtered(lambda p: p.struct_id.country_id.code == 'HK' and p.state == 'draft').action_refresh_from_work_entries()
        return res

    def action_payslip_done(self):
        """
        Force recomputation of future payslips that are potentially already created to ensure the amounts reflect
        the payslip that was just done.
        """
        res = super().action_payslip_done()
        if self.struct_id.country_id.code != 'HK':
            return res
        future_payslips = self.sudo().search([
            ('id', 'not in', self.ids),
            ('state', '=', 'draft'),
            ('employee_id', 'in', self.mapped('employee_id').ids),
            ('date_from', '>=', min(self.mapped('date_to'))),
        ])
        if future_payslips:
            future_payslips.action_refresh_from_work_entries()
        return res
