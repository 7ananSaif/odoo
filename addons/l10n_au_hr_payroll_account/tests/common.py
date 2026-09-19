# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo import Command
from odoo.tests import tagged, new_test_user
from odoo.exceptions import ValidationError
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install_l10n", "post_install", "-at_install", "aba_file")
class L10nPayrollAccountCommon(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('au')
    def setUpClass(cls):
        super().setUpClass()
        # Company Setup
        cls.company = cls.company_data['company']
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= (
                cls.env.ref('account.group_validate_bank_account')
                + cls.env.ref('hr_payroll.group_hr_payroll_manager')
        )
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.resource_calendar = cls.company.resource_calendar_id
        cls.bank_cba = cls.env["res.bank"].create({
            "name": "Commonwealth Bank of Australia",
            "bic": "CTBAAU2S",
            "country": cls.env.ref("base.au").id,
        })
        cls.company_bank_account = cls.env['res.partner.bank'].create({
            "bank_id": cls.bank_cba.id,
            "acc_number": '12344321',
            "acc_type": 'aba',
            "aba_bsb": '123-456',
            "company_id": cls.company.id,
            "partner_id": cls.company.partner_id.id,
        })
        schedule = cls.env.ref("l10n_au_hr_payroll.structure_type_schedule_1")
        cls.default_payroll_structure = cls.env.ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular')
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_journal.write({
            'bank_account_id': cls.company_bank_account.id,
            "aba_fic": "CBA",
            "aba_user_spec": "Test Ltd",
            "aba_user_number": "111111",
        })
        cls.aba_ct = cls.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'aba_ct')
        cls.outbound_manual = cls.bank_journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'manual')
        (cls.aba_ct + cls.outbound_manual).payment_account_id = cls.outbound_payment_method_line.payment_account_id

        # Employees Setup
        cls.employee_user_1 = new_test_user(cls.env, login='mel', groups='hr.group_hr_manager')
        cls.employee_contact_1 = cls.employee_user_1.partner_id
        cls.employee_contact_2 = cls.env['res.partner'].create([{
            'name': "Harry",
            'company_id': cls.env.company.id,
        }])
        cls.bank_accounts_emp_1 = cls.env['res.partner.bank'].create([{
            'acc_number': "123-666",
            'partner_id': cls.employee_contact_1.id,
            'company_id': cls.env.company.id,
            'allow_out_payment': True,
            'aba_bsb': '123456'},
            {'acc_number': "123-777",
            'partner_id': cls.employee_contact_1.id,
            'company_id': cls.env.company.id,
            'allow_out_payment': True,
            'aba_bsb': '123456'}
        ])
        cls.bank_accounts_emp_2 = cls.env['res.partner.bank'].create({
            'acc_number': "123-888",
            'partner_id': cls.employee_contact_2.id,
            'company_id': cls.env.company.id,
            'allow_out_payment': True,
            'aba_bsb': '654321'
        })
        cls.employee_1 = cls.env["hr.employee"].create({
            "name": "Mel Gibson",
            "resource_calendar_id": cls.resource_calendar.id,
            "company_id": cls.company.id,
            "user_id": cls.employee_user_1.id,
            'work_contact_id': cls.employee_contact_1.id,
            'bank_account_ids': [Command.link(cls.bank_accounts_emp_1[1].id)],
            "work_phone": "123456789",
            "work_email": "mel@gmail.com",
            "private_phone": "123456789",
            "private_email": "mel@odoo.com",
            "private_street": "1 Test Street",
            "private_city": "Sydney",
            "private_state_id": cls.env.ref("base.state_au_2").id,
            "private_zip": "2000",
            "private_country_id": cls.env.ref("base.au").id,
            "birthday": date(2000, 1, 1),
            "l10n_au_tfn_declaration": "provided",
            "l10n_au_tfn": "999999661",
            "l10n_au_tax_free_threshold": True,
            "sex": "male",
            "date_version": date(2023, 1, 1),
            "contract_date_start": date(2023, 1, 1),
            "contract_date_end": date(2024, 5, 31),
            "wage_type": "monthly",
            "wage": 5000.0,
            "structure_type_id": schedule.id,
            "schedule_pay": "monthly",
        })
        cls.employee_2 = cls.env["hr.employee"].create({
            "name": "Harry Potter",
            "resource_calendar_id": cls.resource_calendar.id,
            "company_id": cls.company.id,
            'work_contact_id': cls.employee_contact_2.id,
            'bank_account_ids': [Command.link(cls.bank_accounts_emp_2.id)],
            "work_phone": "123456789",
            "private_phone": "123456789",
            "private_email": "harry@odoo.com",
            "private_street": "1 Test Street",
            "private_city": "Sydney",
            "private_state_id": cls.env.ref("base.state_au_2").id,
            "private_zip": "2000",
            "private_country_id": cls.env.ref("base.au").id,
            "birthday": date(2000, 3, 1),
            "l10n_au_tfn_declaration": "provided",
            "l10n_au_tfn": "999999661",
            "l10n_au_tax_free_threshold": True,
            "sex": "female",
            "date_version": date(2023, 1, 1),
            "contract_date_start": date(2023, 1, 1),
            "contract_date_end": False,
            "wage_type": "monthly",
            "wage": 7000.0,
            "structure_type_id": schedule.id,
            "schedule_pay": "monthly",
        })
        super_fund = cls.env['l10n_au.super.fund'].create({
            'name': 'Fund A',
            'abn': '2345678912',
            'address_id': cls.env['res.partner'].create({'name': "Fund A Partner"}).id,
            'usi': "112312312312"
        })
        cls.env['l10n_au.super.account'].create([
            {
                "date_from": date(2023, 6, 1),
                "employee_id": cls.employee_1.id,
                "fund_id": super_fund.id,
                "member_nbr": 1231234123,
            },
            {
                "date_from": date(2023, 6, 1),
                "employee_id": cls.employee_2.id,
                "fund_id": super_fund.id,
                "member_nbr": 1231234123,
            }
        ])

        cls.contract_1 = cls.employee_1.version_id
        cls.contract_2 = cls.employee_2.version_id
        cls.company.l10n_au_hr_super_responsible_id = cls.employee_1
        cls.company.l10n_au_stp_responsible_id = cls.employee_1
        cls.company.ytd_reset_month = "7"
        cls.env['hr.rule.parameter.value'].create({
            "rule_parameter_id": cls.env.ref("l10n_au_hr_payroll.rule_parameter_allowance_laundry").id,
            "date_from": "2023-07-01",
            "parameter_value": {"claimable": 150},
        })

    def _register_payment(self, payslip_run):
        action = payslip_run.action_register_payment()

        payment_register = (
                    self.env["account.payment.register"]
                    .with_context(
                        **action["context"],
                        hr_payroll_payment_register=True,
                        hr_payroll_payment_register_batch=payslip_run.id,
                    )
                    .create({})
                )

        return payment_register._create_payments()

    def _submit_stp(self, stp):
        self.assertTrue(stp, "The STP record should have been created when the payslip was created")
        self.assertEqual(stp.state, "draft", "The STP record should be in draft state")
        stp.submit_date = stp.submit_date or date.today()
        action = self.env['l10n_au.stp.submit'].create(
            {'l10n_au_stp_id': stp.id}
        )
        with self.assertRaises(ValidationError):
            action.action_submit()
        action.stp_terms = True
        action.action_submit()

        self.assertTrue(stp.xml_file, "The XML file should have been generated")
        self.assertEqual(stp.state, "sent", "The STP record should be in sent state")

    def _prepare_payslip_run(self, employee_ids, extra_input_xml_ids=None, start_date=None, end_date=None):
        input_xml_ids = extra_input_xml_ids
        if not input_xml_ids:
            input_xml_ids = {
                "l10n_au_hr_payroll.input_laundry_2": 100,
                "l10n_au_hr_payroll.input_laundry_3": 100,
                "l10n_au_hr_payroll.input_gross_director_fee": 100,
                "l10n_au_hr_payroll.input_bonus_commissions_overtime": 100,
                "l10n_au_hr_payroll.input_fringe_benefits_amount": 2000,
            }

        payslip_run = self.env["hr.payslip.run"].create(
            {
                "date_start": start_date or "2024-01-01",
                "date_end": end_date or "2024-01-31",
                "name": "January Batch",
                "company_id": self.company.id,
            }
        )

        payslip_run.generate_payslips(employee_ids=employee_ids.ids)
        payslip_run.slip_ids.write({"input_line_ids": [(0, 0, {
            "input_type_id": self.env.ref(input_id).id,
            "amount": amount,
            }) for input_id, amount in input_xml_ids.items()
        ]})
        payslip_run.slip_ids.compute_sheet()
        payslip_run.action_validate()
        return payslip_run
