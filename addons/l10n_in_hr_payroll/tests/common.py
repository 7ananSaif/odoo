# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Bank = cls.env['res.partner.bank']
        cls.Employee = cls.env['hr.employee']
        cls.PayslipRun = cls.env['hr.payslip.run']
        cls.Company = cls.env['res.company']
        cls.partner = cls.env.ref('base.partner_admin')
        cls.bank_1 = cls.env.ref('base.res_bank_1')
        cls.in_country = cls.env.ref('base.in')
        cls.rd_dept = cls.env['hr.department'].create({
            'name': 'Research and Development',
        })
        cls.employee_fp = cls.env.ref('hr.employee_admin')

        cls.company_in = cls.Company.create({
            'name': 'Company IN',
            'country_id': cls.env.ref('base.in').id,
            'l10n_in_esic': True,
            'l10n_in_pt': True,
            'l10n_in_provident_fund': True,
        })

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_in.ids))

        cls.in_bank = cls.env['res.bank'].create({
            'name': 'Bank IN',
            'bic': 'ABCD0123456'
        })

        cls.rahul_emp = cls.Employee.create({
            'name': 'Rahul',
            'country_id': cls.in_country.id,
            'department_id': cls.rd_dept.id,
            'company_id': cls.company_in.id,
            'l10n_in_esic_number': 93874944361284657,
            'date_version': date(2023, 1, 1),
            'contract_date_start': date(2023, 1, 1),
            'contract_date_end':  date(2023, 1, 31),
            'wage': 5000.0,
            'hr_responsible_id': cls.employee_fp.id,
            'l10n_in_basic_percentage': 0.35,
            'l10n_in_hra_percentage': 0.4,
            'l10n_in_standard_allowance': 30,
            'l10n_in_performance_bonus_percentage': 0.3,
            'l10n_in_leave_travel_percentage': 0.3,
            'l10n_in_medical_insurance': 560.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_gratuity_percentage': 0.0481,
            'l10n_in_esic_employee_amount': 20.0,
            'l10n_in_esic_employer_amount': 20.0,
        })

        cls.jethalal_emp = cls.Employee.create({
            'name': 'Jethalal',
            'country_id': cls.in_country.id,
            'department_id': cls.rd_dept.id,
            'company_id': cls.company_in.id,
            'l10n_in_esic_number': 93487475100284657,
            'date_version': date(2023, 1, 1),
            'contract_date_start': date(2023, 1, 1),
            'contract_date_end':  date(2023, 1, 31),
            'wage': 5000.0,
            'hr_responsible_id': cls.employee_fp.id,
            'l10n_in_basic_percentage': 0.35,
            'l10n_in_hra_percentage': 0.4,
            'l10n_in_standard_allowance': 40,
            'l10n_in_performance_bonus_percentage': 0.3,
            'l10n_in_leave_travel_percentage': 0.3,
            'l10n_in_medical_insurance': 560.0,
            'l10n_in_insured_spouse': True,
            'l10n_in_gratuity_percentage': 0.0481,
            'l10n_in_esic_employee_amount': 20.0,
            'l10n_in_esic_employer_amount': 20.0,
        })

        cls.res_bank = cls.Bank.create({
            'acc_number': '3025632343043',
            'partner_id': cls.rahul_emp.work_contact_id.id,
            'acc_type': 'bank',
            'bank_id': cls.in_bank.id,
            'allow_out_payment': True,
        })
        cls.rahul_emp.bank_account_ids = [Command.link(cls.res_bank.id)]

        cls.res_bank_1 = cls.Bank.create({
            'acc_number': '3025632343044',
            'partner_id': cls.jethalal_emp.work_contact_id.id,
            'acc_type': 'bank',
            'bank_id': cls.in_bank.id,
            'allow_out_payment': True,
        })
        cls.jethalal_emp.bank_account_ids = [Command.link(cls.res_bank_1.id)]

        cls.contract_rahul = cls.rahul_emp.version_id
        cls.contract_jethalal = cls.jethalal_emp.version_id

        cls.contract_rahul._compute_l10n_in_esic_employee_percentage()
        cls.contract_rahul._compute_l10n_in_esic_employer_percentage()
        cls.contract_jethalal._compute_l10n_in_esic_employee_percentage()
        cls.contract_jethalal._compute_l10n_in_esic_employer_percentage()
