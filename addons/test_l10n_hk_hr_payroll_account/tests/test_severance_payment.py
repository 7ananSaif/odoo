# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY

from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSeverancePay(TestL10NHkHrPayrollAccountCommon):
    """
    These tests are based on numbers generated using the official Labour Department calculator.
    """
    def test_severance_payment_no_split(self):
        """ Validate calculation of severance payment without split (the employment period started after May 2025). """
        date_start = date(2026, 1, 1)
        date_end = date(2027, 12, 31)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            "l10n_hk_member_class_id": self.member_class.id,
        })

        for dt in rrule(MONTHLY, dtstart=date_start, until=date_end + relativedelta(day=31)):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        payslip = self._generate_payslip(
            date_end, date(2027, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_severance_payment').id,
        )
        result = {
            'SEVERANCE_PAYMENT_POST_TRANSITION': 26933.33,
            'SEVERANCE_PAYMENT': 26933.33,
            'NET': 26933.33,
        }
        self._validate_payslip(payslip, result)

    def test_severance_payment_split(self):
        """ Validate calculation of severance payment with split (the employment period started before May 2025). """
        date_start = date(2025, 1, 1)
        date_end = date(2027, 12, 31)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            "l10n_hk_member_class_id": self.member_class.id,
        })

        for dt in rrule(MONTHLY, dtstart=date_start, until=date_end):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()
        payslip = self._generate_payslip(
            date_end, date(2027, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_severance_payment').id,
        )
        # Note that this differs from 1 cent compared to their calculator, due to them rounding at the intermediate steps.
        # We assume that this is for visual representation, and that keeping full accuracy is more correct.
        result = {
            'SEVERANCE_PAYMENT_PRE_TRANSITION': 4427.4,
            'SEVERANCE_PAYMENT_POST_TRANSITION': 35947.91,
            'SEVERANCE_PAYMENT': 40375.3,
            'NET': 40375.3,
        }
        self._validate_payslip(payslip, result)

    def test_severance_payment_mpf_offsetting(self):
        """ Validate calculation of severance payment when MPF offsetting is in use. """
        date_start = date(2025, 1, 1)
        date_end = date(2027, 12, 31)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            "l10n_hk_member_class_id": self.member_class.id,
        })
        self.employee.l10n_hk_member_class_ct_eevc_id.contribution_option = 'percentage'

        for dt in rrule(MONTHLY, dtstart=date_start, until=date_end):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        self.contract.company_id.l10n_hk_use_mpf_offsetting = True
        payslip = self._generate_payslip(
            date_end, date(2027, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_severance_payment').id,
        )
        result = {
            'SEVERANCE_PAYMENT_PRE_TRANSITION': 4427.4,
            'SEVERANCE_PAYMENT_POST_TRANSITION': 35947.91,
            'SEVERANCE_PAYMENT': 40375.3,
            'SEVERANCE_PAYMENT_PRE_TRANSITION_OFFSET': -4427.4,
            'SEVERANCE_PAYMENT_POST_TRANSITION_OFFSET': -35351.76,
            'NET': 596.15,
        }
        self._validate_payslip(payslip, result)

    def test_severance_payment_mpf_offsetting_post_transition_only(self):
        """ Validate calculation of severance payment when MPF offsetting is in use. """
        date_start = date(2025, 10, 1)
        date_end = date(2027, 12, 31)
        self.contract.write({
            'date_version': date_start,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            "l10n_hk_member_class_id": self.member_class.id,
        })
        self.employee.l10n_hk_member_class_ct_eevc_id.contribution_option = 'percentage'

        for dt in rrule(MONTHLY, dtstart=date_start, until=date_end):
            payslip = self._generate_payslip(dt.date(), dt.date() + relativedelta(day=31))
            payslip.action_payslip_done()
            payslip.action_payslip_paid()

        self.contract.company_id.l10n_hk_use_mpf_offsetting = True
        payslip = self._generate_payslip(
            date_end, date(2027, 12, 31),
            struct_id=self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_severance_payment').id,
        )
        result = {
            'SEVERANCE_PAYMENT_POST_TRANSITION': 30318.4,
            'SEVERANCE_PAYMENT': 30318.4,
            'SEVERANCE_PAYMENT_POST_TRANSITION_OFFSET': -29543.88,
            'NET': 774.52,
        }
        self._validate_payslip(payslip, result)
