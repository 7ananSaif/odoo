# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.fields import Datetime
from dateutil.rrule import rrule, MONTHLY


def _generate_payslips(env):
    # Do this only when demo data is activated
    if env.ref('base.demo_company_hk', raise_if_not_found=False):
        anthony = env.ref('l10n_hk_hr_payroll.hr_employee_anthony', raise_if_not_found=False)
        natalie = env.ref('l10n_hk_hr_payroll.hr_employee_natalie', raise_if_not_found=False)
        if not anthony and not natalie:
            return

        # Anthony, last year's payslip from june to december
        if anthony:
            _prepare_demo_batches(env, anthony, Datetime.now() + relativedelta(years=-1, month=6), Datetime.now() + relativedelta(years=-1, month=12))

        # Both employees, current year's payslip from January to this month.
        employees = anthony | natalie
        if employees:
            _prepare_demo_batches(env, employees, Datetime.now() + relativedelta(month=1))


def _prepare_demo_batches(env, employees, start_month, end_month=False):
    payrun_date = start_month + relativedelta(day=1)
    end_date = end_month or date.today()
    payruns_data = []
    for dt in rrule(MONTHLY, dtstart=payrun_date, until=end_date):
        payruns_data.append({
            'date_start': dt,
            'date_end': dt + relativedelta(day=31),
        })

    payruns = env['hr.payslip.run'].with_company(env.ref('base.demo_company_hk')).create(payruns_data)
    for i, payrun in enumerate(payruns):
        payrun.generate_payslips(employee_ids=employees.ids)
        if i < (len(payruns) - 1) or end_date != date.today():
            # We process all payruns one at a time, because otherwise rules depending on the previous payslips being validated wouldn't work.
            payrun.action_validate()
            payrun.action_paid()
