# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io
from datetime import date

from odoo.fields import Command
from odoo.tests import tagged

from .common import TestL10NHkHrPayrollAccountCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestEmpf(TestL10NHkHrPayrollAccountCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # For ease of testing, we don't want the december payslip to vary due to this feature.
        cls.env.company.l10n_hk_eoy_pay_month = False

    # -------------------------------------------------------------------
    # The following scenarios come from the official eMPF specifications.
    # -------------------------------------------------------------------

    def test_scenario_1(self):
        """
        Report of new member who just joined the company within a month, no contribution will be made, not joining the voluntary contribution
        """
        self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2021, 12, 1),
                'contract_date_start': date(2021, 12, 1),
                'wage': 20000.0,
                'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
                'l10n_hk_mpf_registration_status': 'next_contribution',
                'l10n_hk_mpf_contribution_start': 'at_due_date',
                'l10n_hk_mpf_scheme_join_date': date(2021, 12, 1),
                'identification_id': 'Z683365A',
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'private_phone': '98651234',
                'private_email': 'defghi@address.ik',
                'birthday': date(2002, 2, 2),
                'l10n_hk_surname': 'AU-YEUNG',
                'l10n_hk_given_name': 'FUNG',
                'l10n_hk_name_in_chinese': '歐陽 峰',
                'sex': 'male',
            }
        )

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'new_employees')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z683365A", "20211201", "N",  # General info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # Contribution info
                "M", "AU-YEUNG", "FUNG", "歐陽 峰", "", "20211201", "20020202", "", "", "NEW", "", "", "defghi@address.ik", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_2(self):
        """
        Report of new member who just joined the company within a month, no contribution will be made, joining the voluntary contribution
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2021, 12, 1),
                "contract_date_start": date(2021, 12, 1),
                "wage": 20000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_registration_status": "next_contribution",
                "l10n_hk_mpf_contribution_start": "at_due_date",
                "l10n_hk_mpf_scheme_join_date": date(2021, 12, 1),
                "identification_id": "Z936829A",
                "l10n_hk_internet": 200.0,
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "defghi@address.ik",
                "birthday": date(1999, 4, 1),
                "l10n_hk_surname": "AU-YEUNG",
                "l10n_hk_given_name": "FUNG",
                "l10n_hk_name_in_chinese": "歐陽 峰",
                "sex": "male",
            },
        )

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'new_employees')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z936829A", "20211201", "N",  # General info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # Contribution info
                "M", "AU-YEUNG", "FUNG", "歐陽 峰", "", "20211201", "19990401", "GT1", "20211201", "NEW", "", "", "defghi@address.ik", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_3(self):
        """
        Report of new member who has joined the company for 60 days, and contribution for the employee is made, not joining the voluntary contribution
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2021, 11, 1),
                "contract_date_start": date(2021, 11, 1),
                "wage": 28000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_scheme_join_date": date(2021, 11, 1),
                "identification_id": "C6686689",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        self._create_payrun_and_report(date(2021, 11, 1), date(2021, 11, 30))  # Register payslips for November.
        employee.l10n_hk_mpf_registration_status = "next_contribution"
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "C6686689", "20211101", "N",  # General info
                "", "", "20211101", "20211130", "", "", "", "28000.0", "", "1400.0", "", "", "", "", "", "", "1400.0",  # Contribution info
                "F", "Chan", "Suzan", "", "", "20211101", "19810527", "", "", "NEW", "", "", "suzanchan@webdoc.com", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ],
            [
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "C6686689", "20211101", "N",  # General info
                "", "", "20211201", "20211231", "", "", "", "28000.0", "", "1400.0", "1400.0", "", "", "", "", "", "2800.0",  # Contribution info
                "F", "Chan", "Suzan", "", "", "20211101", "19810527", "", "", "NEW", "", "", "suzanchan@webdoc.com", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_4(self):
        """
        Make contribution to existing members without voluntary contribution
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2013, 1, 12),
                "contract_date_start": date(2013, 1, 12),
                "wage": 18000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_account_number": "2958473832",
                "l10n_hk_staff_number": "S399384",
                "l10n_hk_mpf_scheme_join_date": date(2013, 1, 12),
                "identification_id": "Z3882978",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z3882978", "20130112", "E",  # General info
                "2958473832", "S399384", "20211201", "20211231", "", "", "", "18000.0", "", "900.0", "900.0", "", "", "", "", "", "1800.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_5(self):
        """
        Make contribution to existing members with voluntary contribution
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref(
                "l10n_hk_hr_payroll.structure_type_employee_cap57"
            ),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2011, 1, 2),
                "contract_date_start": date(2011, 1, 2),
                "wage": 21500.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_scheme_join_date": date(2011, 1, 2),
                "identification_id": "Z9881329",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        employee.l10n_hk_member_class_ct_eevc_id.unlink()
        employee.l10n_hk_member_class_ct_ervc_id.write({
            'contribution_option': 'fixed',
            'amount': 1000,
        })
        employee.l10n_hk_member_class_ct_ervc2_id = self.env['l10n_hk.member.class.contribution.type'].create({
            'member_class_id': self.member_class.id,
            'contribution_type': 'employer_2',
            'contribution_option': 'fixed',
            'amount': 1000,
        })
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z9881329", "20110102", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "21500.0", "", "1075.0", "1075.0", "1000.0", "1000.0", "", "", "", "4150.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_6(self):
        """
        An employee has terminated with Contract Ends in last contribution period with LSP/SP
        Because the Monthly Relevant Income is less than $7100, no Employee Mandatory Contribution is required (As of 2023/01/16)
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2011, 1, 2),
                "contract_date_start": date(2011, 1, 2),
                "wage": 11071.43,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2011, 1, 2),
                "identification_id": "G9088333",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        # Terminate the employee
        departure_notice = self.env["hr.departure.wizard"].create({
            "employee_ids": [Command.link(employee.id)],
            "departure_reason_id": self.env.ref('l10n_hk_hr_payroll_empf.hr_departure_reason_contract_end').id,
            "departure_date": date(2021, 12, 14),
            "departure_description": "",
            "set_date_end": True,
        })
        departure_notice.with_context(toggle_active=True).action_register_departure()
        # Register a long service pay for the employee (requires a previous month slip for the calculation)
        payslip = self._generate_payslip(
            date(2021, 11, 1),
            date(2021, 11, 30),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()
        payslip = self._generate_payslip(
            date(2021, 12, 1),
            date(2021, 12, 31),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_long_service_payment").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "G9088333", "20110102", "T",  # General info
                "", "", "20211201", "20211231", "", "", "", "5000.0", "", "250.0", "", "", "", "", "", "", "250.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "20211214", "CONTRACT_END", "L"  # Termination info
            ]]
        )

    def test_scenario_7(self):
        """
        An employee has terminated with resignation in last contribution period without LSP/SP
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2011, 1, 2),
                "contract_date_start": date(2011, 1, 2),
                "wage": 21312.5,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_scheme_join_date": date(2011, 1, 2),
                "identification_id": "Z6833676",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        employee.l10n_hk_member_class_ct_eevc_id.unlink()
        employee.l10n_hk_member_class_ct_ervc_id.write({
            'contribution_option': 'fixed',
            'amount': 200,
        })
        employee.l10n_hk_member_class_ct_ervc2_id = self.env['l10n_hk.member.class.contribution.type'].create({
            'member_class_id': self.member_class.id,
            'contribution_type': 'employer_2',
            'contribution_option': 'fixed',
            'amount': 200,
        })
        # Terminate the employee
        departure_notice = self.env["hr.departure.wizard"].create({
            "employee_ids": [Command.link(employee.id)],
            "departure_reason_id": self.env.ref('hr.departure_resigned').id,
            "departure_date": date(2021, 12, 16),
            "departure_description": "",
            "set_date_end": True,
        })
        departure_notice.with_context(toggle_active=True).action_register_departure()
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))

        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z6833676", "20110102", "T",  # General info
                "", "", "20211201", "20211231", "", "", "", "11000.0", "", "550.0", "550.0", "200.0", "200.0", "", "", "", "1500.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "20211216", "RESIGN", ""  # Termination info
            ]]
        )

    def test_scenario_8(self):
        """
        An employee who took unpaid leave (doesn't have any relevant income) during the contribution period, not joining Voluntary Contribution
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2014, 8, 1),
                "contract_date_start": date(2014, 8, 1),
                "wage": 21312.5,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2014, 8, 1),
                "identification_id": "C6686689",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        leave = self.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'request_date_from': date(2021, 12, 1),
            'request_date_to': date(2021, 12, 31),
            'holiday_status_id': self.env.ref('hr_holidays.l10n_hk_leave_type_unpaid_leave').id,
        })
        leave.action_approve()

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "C6686689", "20140801", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "0.0", "", "0.0", "0.0", "", "", "", "", "", "0.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    # Scenarios 9 & 10 are for casual employees, which we do not yet support

    def test_scenario_11(self):
        """
        An employer who makes contributions for two existing normal employees, and one of these members (A5270734) has incurred a surcharge from the contribution period of the previous month
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2009, 4, 2),
                "contract_date_start": date(2009, 4, 2),
                "wage": 21500.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2009, 4, 2),
                "identification_id": "X7623491",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2008, 10, 4),
                "contract_date_start": date(2008, 10, 4),
                "wage": 11000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2008, 10, 4),
                "identification_id": "A5270734",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "defghi@address.ik",
                "birthday": date(1999, 4, 1),
                "l10n_hk_surname": "AU-YEUNG",
                "l10n_hk_given_name": "FUNG",
                "sex": "male",
            },
        )
        employee.name = 'Another HK Employee'  # We need different names for the ordering

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        # Add a surcharge line to the report
        report.contribution_line_ids = [Command.create({
            'status': 'E',
            'employee_id': employee.id,
            'employee_surcharge': 100,
            'employer_surcharge': 100,
            'contribution_start_date': date(2021, 11, 1),
            'contribution_end_date': date(2021, 11, 30),
        })]

        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "A5270734", "20081004", "E",  # General info
                "", "", "20211101", "20211130", "", "", "", "0.0", "", "0.0", "0.0", "", "", "", "100.0", "100.0", "200.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ], [
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "A5270734", "20081004", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "11000.0", "", "550.0", "550.0", "", "", "", "", "", "1100.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ], [
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "X7623491", "20090402", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "21500.0", "", "1075.0", "1075.0", "", "", "", "", "", "2150.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_12(self):
        """
        Make contribution to existing members without voluntary contribution, and Relevant Income is more than $30,000, so the Employer and Employee Mandatory Contribution is capped at $1,500
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2019, 12, 3),
                "contract_date_start": date(2019, 12, 3),
                "wage": 55000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_account_number": "2958473832",
                "l10n_hk_staff_number": "S399384",
                "l10n_hk_mpf_scheme_join_date": date(2019, 12, 3),
                "identification_id": "N4895574",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "N4895574", "20191203", "E",  # General info
                "2958473832", "S399384", "20211201", "20211231", "", "", "", "55000.0", "", "1500.0", "1500.0", "", "", "", "", "", "3000.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_13(self):
        """
        Make contribution to existing members without voluntary contribution, and Relevant Income is less than $7,100,
        so the Employer Mandatory Contribution is calculated as Relevant income x 5%, no Employee's Mandatory Contribution is required
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2013, 1, 12),
                "contract_date_start": date(2013, 1, 12),
                "wage": 6500.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_account_number": "2958473832",
                "l10n_hk_staff_number": "S399384",
                "l10n_hk_mpf_scheme_join_date": date(2013, 1, 12),
                "identification_id": "Z3882978",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "Z3882978", "20130112", "E",  # General info
                "2958473832", "S399384", "20211201", "20211231", "", "", "", "6500.0", "", "325.0", "", "", "", "", "", "", "325.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_14(self):
        """
        Enrol an exempt person who enrols to a MPF scheme in order to join the voluntary contribution
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2021, 12, 14),
                "contract_date_start": date(2021, 12, 14),
                "wage": 20000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_registration_status": "next_contribution",
                "l10n_hk_mpf_contribution_start": "at_due_date",
                "l10n_hk_mpf_scheme_join_date": date(2021, 12, 14),
                "l10n_hk_mpf_exempt": True,
                "passport_id": "AP9929922C",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "random123@example.com",
                "birthday": date(1985, 4, 12),
                "l10n_hk_surname": "Cheung",
                "l10n_hk_given_name": "Mei Na",
                "l10n_hk_name_in_chinese": "張 美娜",
                "sex": "female",
            },
        )
        self.member_class.name = 'MT1'

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'new_employees')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "PASSPORT", "AP9929922C", "20211214", "N",  # General info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # Contribution info
                "F", "Cheung", "Mei Na", "張 美娜", "", "20211214", "19850412", "MT1", "20211214", "EXEMPT", "", "", "random123@example.com", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_15(self):
        """
        An exempt person who has enrolled to a MPF scheme to make voluntary contribution based on monthly salary
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref(
                "l10n_hk_hr_payroll.structure_type_employee_cap57"
            ),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2019, 8, 25),
                "contract_date_start": date(2019, 8, 25),
                "wage": 28000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_scheme_join_date": date(2019, 8, 25),
                "l10n_hk_mpf_exempt": True,
                "passport_id": "IND033234443",
                "l10n_hk_internet": 200.0,
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        employee.l10n_hk_member_class_ct_eevc_id.write({
            'contribution_option': 'percentage',
            'definition_of_income': 'basic_salary',
            'amount': 3,
        })
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "PASSPORT", "IND033234443", "20190825", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "28200.0", "28000.0", "", "", "840.0", "", "840.0", "", "", "1680.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_16(self):
        """
        An employee who retired within the contribution period of 2021/12/01 - 2021/12/31,
        last employment date on 2021/12/01 with no pay leave, so no Relevant Income in that period, with Long Service Payment's request
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2016, 10, 13),
                "contract_date_start": date(2016, 10, 13),
                "wage": 11071.43,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2016, 10, 13),
                "identification_id": "H9644190",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        # Terminate the employee
        departure_notice = self.env["hr.departure.wizard"].create({
            "employee_ids": [Command.link(employee.id)],
            "departure_reason_id": self.env.ref('hr.departure_retired').id,
            "departure_date": date(2021, 12, 1),
            "departure_description": "",
            "set_date_end": True,
        })
        departure_notice.with_context(toggle_active=True).action_register_departure()
        leave = self.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'request_date_from': date(2021, 12, 1),
            'request_date_to': date(2021, 12, 1),
            'holiday_status_id': self.env.ref('hr_holidays.l10n_hk_leave_type_unpaid_leave').id,
        })
        leave.action_approve()

        # Register a long service pay for the employee (requires a previous month slip for the calculation)
        payslip = self._generate_payslip(
            date(2021, 11, 1),
            date(2021, 11, 30),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()
        payslip = self._generate_payslip(
            date(2021, 12, 1),
            date(2021, 12, 31),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_long_service_payment").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        terminated_employee_lines = report.contribution_line_ids.filtered(
            lambda line: line.status == "T" and not line.total_contributions
        )
        self.assertFalse(terminated_employee_lines.termination_payment_type)  # No contributions, so default to False
        terminated_employee_lines.termination_payment_type = 'L'  # test the manual override

        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'terminated_employees')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "H9644190", "20161013", "T",  # General info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "20211201", "RETIRE", "L"  # Termination info
            ]]
        )

    def test_scenario_17(self):
        """
        An employer enrols and makes contribution to an employee who has employed less than 60 days, so both the 'Member Contribution' and 'New Member' sections need to be filled, not joining VC
        """
        self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2021, 12, 7),
                "contract_date_start": date(2021, 12, 7),
                "wage": 22320,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_registration_status": "next_contribution",
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_scheme_join_date": date(2021, 12, 7),
                "identification_id": "F435122A",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "mail1234@bmail.com",
                "birthday": date(1989, 9, 17),
                "l10n_hk_surname": "Li",
                "l10n_hk_given_name": "Wei",
                'l10n_hk_name_in_chinese': '李 偉',
                "sex": "female",
            },
        )
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "F435122A", "20211207", "N",  # General info
                "", "", "20211201", "20211231", "", "", "", "18000.0", "", "900.0", "", "", "", "", "", "", "900.0",  # Contribution info
                "F", "Li", "Wei", "李 偉", "", "20211207", "19890917", "", "", "NEW", "", "", "mail1234@bmail.com", "852", "98651234",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    def test_scenario_18(self):
        """
        An employee who has been employed more than 2 years, and redundant within the contribution period of 2021/12/01 - 2021/12/31 on 2021/12/18,
        the employee has relevant income and contribution within the period, and request for Severance Payment
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2017, 7, 14),
                "contract_date_start": date(2017, 7, 14),
                "wage": 16705.56,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2017, 7, 14),
                "identification_id": "H8977285",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        # Terminate the employee
        departure_notice = self.env["hr.departure.wizard"].create({
            "employee_ids": [Command.link(employee.id)],
            "departure_reason_id": self.env.ref('l10n_hk_hr_payroll_empf.hr_departure_reason_redundancy').id,
            "departure_date": date(2021, 12, 18),
            "departure_description": "",
            "set_date_end": True,
        })
        departure_notice.with_context(toggle_active=True).action_register_departure()

        # Register a severance pay for the employee (requires a previous month slip for the calculation)
        payslip = self._generate_payslip(
            date(2021, 11, 1),
            date(2021, 11, 30),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()
        payslip = self._generate_payslip(
            date(2021, 12, 1),
            date(2021, 12, 31),
            struct_id=self.env.ref("l10n_hk_hr_payroll.hr_payroll_structure_cap57_severance_payment").id,
            employee_id=employee.id,
            version_id=employee.version_id.id,
        )
        payslip.action_validate()
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))

        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "H8977285", "20170714", "T",  # General info
                "", "", "20211201", "20211231", "", "", "", "9700.01", "", "485.0", "485.0", "", "", "", "", "", "970.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "20211218", "REDUNDANCY", "S"  # Termination info
            ]]
        )

    def test_scenario_19(self):
        """
        An employee who has been employed less than 2 years, and redundant within the contribution period of 2021/12/01 - 2021/12/31 on 2021/12/18,
        the employee has relevant income and contribution within the period, but the employee is not entitled to Severance Payment
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref("l10n_hk_hr_payroll.structure_type_employee_cap57"),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2020, 11, 23),
                "contract_date_start": date(2020, 11, 23),
                "wage": 14811.1,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_mpf_scheme_join_date": date(2020, 11, 23),
                "identification_id": "R4349961",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        # Terminate the employee
        departure_notice = self.env["hr.departure.wizard"].create({
            "employee_ids": [Command.link(employee.id)],
            "departure_reason_id": self.env.ref('l10n_hk_hr_payroll_empf.hr_departure_reason_redundancy').id,
            "departure_date": date(2021, 12, 18),
            "departure_description": "",
            "set_date_end": True,
        })
        departure_notice.with_context(toggle_active=True).action_register_departure()
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))

        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "R4349961", "20201123", "T",  # General info
                "", "", "20211201", "20211231", "", "", "", "8600.0", "", "430.0", "430.0", "", "", "", "", "", "860.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "20211218", "REDUNDANCY", ""  # Termination info
            ]]
        )

    def test_scenario_20(self):
        """
        An employer has setup two separate voluntary rules on the Employer Voluntary Contribution, so the employer can make Employer Voluntary Contribution in two separate accounts
        """
        employee = self._setup_employee(
            country=self.env.ref("base.hk"),
            structure_type=self.env.ref(
                "l10n_hk_hr_payroll.structure_type_employee_cap57"
            ),
            resource_calendar=self.resource_calendar,
            contract_fields={
                "date_version": date(2014, 10, 27),
                "contract_date_start": date(2014, 10, 27),
                "wage": 32000.0,
                "l10n_hk_mpf_scheme_id": self.mpf_scheme.id,
                "l10n_hk_mpf_contribution_start": "immediate",
                "l10n_hk_mpf_registration_status": "registered",
                "l10n_hk_member_class_id": self.member_class.id,
                "l10n_hk_mpf_scheme_join_date": date(2014, 10, 27),
                "identification_id": "D6242589",
            },
            employee_fields={
                "private_phone": "98651234",
                "private_email": "suzanchan@webdoc.com",
                "birthday": date(1981, 5, 27),
                "l10n_hk_surname": "Chan",
                "l10n_hk_given_name": "Suzan",
                "sex": "female",
            },
        )
        employee.l10n_hk_member_class_ct_eevc_id.write({
            'contribution_option': 'fixed',
            'amount': 200,
        })
        employee.l10n_hk_member_class_ct_ervc_id.write({
            'contribution_option': 'percentage',
            'amount': 2.5,
        })
        employee.l10n_hk_member_class_ct_ervc2_id = self.env['l10n_hk.member.class.contribution.type'].create({
            'member_class_id': self.member_class.id,
            'contribution_type': 'employer_2',
            'contribution_option': 'percentage',
            'amount': 1.25,
        })
        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                "MT00298", "123456789012", "MLY", "", "20211201", "20211231", "", "REE", "HKID", "D6242589", "20141027", "E",  # General info
                "", "", "20211201", "20211231", "", "", "", "32000.0", "", "1500.0", "1500.0", "800.0", "400.0", "200.0", "", "", "4400.0",  # Contribution info
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",  # New member info
                "", "", ""  # Termination info
            ]]
        )

    # Scenario 21 is about correcting past payslips and back-paying them.
    # We do support this when creating the eMPF report lines manually, but no specific system to test.

    # ----------------------------------------
    # Additional tests for some specific cases
    # ----------------------------------------

    def test_phone_format(self):
        """
        Test the phone formatting on new member and the different possible matches.
        """
        employee = self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2021, 12, 1),
                'contract_date_start': date(2021, 12, 1),
                'wage': 20000.0,
                'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
                'l10n_hk_mpf_registration_status': 'next_contribution',
                'l10n_hk_mpf_contribution_start': 'at_due_date',
                'l10n_hk_mpf_scheme_join_date': date(2021, 12, 1),
                'identification_id': 'Z683365A',
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'private_phone': '98651234',
                'private_email': 'defghi@address.ik',
                'birthday': date(2002, 2, 2),
                'l10n_hk_surname': 'AU-YEUNG',
                'l10n_hk_given_name': 'FUNG',
                'l10n_hk_name_in_chinese': '歐陽 峰',
                'sex': 'male',
            }
        )

        report = self._create_payrun_and_report(date(2021, 12, 1), date(2021, 12, 31))
        # Note: in case of failure, the action will raise a user error, so just calling it is enough for this test.

        # Case 1: Employee with local number, and country set.
        report.action_generate_report()

        # Case 2: Employee with international number, no country set.
        employee.write({
            'country_id': False,
            'private_phone': '+85298651234'
        })
        report.action_generate_report()

        # Case 3: Employee with local number, no country set, company country is set.
        employee.private_phone = '98651234'
        report.action_generate_report()

    def test_start_middle_month_and_due_date(self):
        """
        Onboard a new employee on January 1st.
        Employee is not exempt of MPF, and will not use voluntary contributions.
        Employee will be onboarded automatically at the next contribution report, but only contribute when due date arrives. (feb in this case)
        """
        self._setup_employee(
            country=self.env.ref('base.hk'),
            structure_type=self.env.ref('l10n_hk_hr_payroll.structure_type_employee_cap57'),
            resource_calendar=self.resource_calendar,
            contract_fields={
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'wage': 20000.0,
                'l10n_hk_mpf_scheme_id': self.mpf_scheme.id,
                'l10n_hk_mpf_account_number': '123987456',
                'l10n_hk_mpf_registration_status': 'next_contribution',
                'l10n_hk_mpf_contribution_start': 'at_due_date',
                'l10n_hk_mpf_scheme_join_date': date(2025, 1, 1),
                'identification_id': '12345679',
                'l10n_hk_internet': 200.0,
            },
            employee_fields={
                'private_phone': '98651234',
                'private_email': 'hkemployee@hkcompany.hk',
                'birthday': date(2005, 2, 5),
                'l10n_hk_surname': 'HK',
                'l10n_hk_given_name': 'Employee',
            }
        )

        # First month, registered and employer's contribution
        report = self._create_payrun_and_report(date(2025, 1, 1), date(2025, 1, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'new_employees')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[
                 'MT00298', '123456789012', 'MLY', '', '20250101', '20250131', '', 'REE', 'HKID', '12345679', '20250101', 'N',  # General info
                 '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',  # Contribution info
                 'O', 'HK', 'Employee', '', '', '20250101', '20050205', '', '', 'NEW', '', '', 'hkemployee@hkcompany.hk', '852', '98651234',  # New member info
                 '', '', ''  # Termination info
            ]]
        )
        # We expect no contribution amounts on the line, to match the csv, even though ERMC would be in the payslip
        self.assertRecordValues(report.contribution_line_ids, [{
            'ermc': 0.0,
        }])
        # Second month, empty, skip validation as it would raise
        report = self._create_payrun_and_report(date(2025, 2, 1), date(2025, 2, 28), validate_report=False)
        self.assertEqual(len(report.contribution_line_ids), 0)  # We already registered the employee in january and payment isn't due before March, so it will be empty
        # Third month, employee already exists, and will have three month of contributions
        report = self._create_payrun_and_report(date(2025, 3, 1), date(2025, 3, 31))
        report.action_generate_report()
        csv_report = self._get_csv_reports_per_type(report, 'contributions')
        reader = csv.reader(io.StringIO(csv_report.raw.decode()), delimiter=",")
        lines = list(reader)
        self.assertListEqual(
            lines,
            [[  # Back-pay of the first month
                 'MT00298', '123456789012', 'MLY', '', '20250301', '20250331', '', 'REE', 'HKID', '12345679', '20250101', 'E',  # General info
                 '123987456', '', '20250101', '20250131', '', '', '', '20200.0', '', '1010.0', '', '', '', '', '', '', '1010.0',  # Contribution info
                 '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',  # New member info
                 '', '', ''  # Termination info
            ], [  # Back-pay of the second month
                 'MT00298', '123456789012', 'MLY', '', '20250301', '20250331', '', 'REE', 'HKID', '12345679', '20250101', 'E',  # General info
                 '123987456', '', '20250201', '20250228', '', '', '', '20200.0', '', '1010.0', '1010.0', '', '', '', '', '', '2020.0',  # Contribution info
                 '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',  # New member info
                 '', '', ''  # Termination info
            ], [  # Regular contributions starting on the third month
                 'MT00298', '123456789012', 'MLY', '', '20250301', '20250331', '', 'REE', 'HKID', '12345679', '20250101', 'E',  # General info
                 '123987456', '', '20250301', '20250331', '', '', '', '20200.0', '', '1010.0', '1010.0', '', '', '', '', '', '2020.0',  # Contribution info
                 '', '', '', '', '', '', '', '', '', '', '', '', '', '', '',  # New member info
                 '', '', ''  # Termination info
            ]]
        )
        # This time, we will see the ermc for all lines in the form.
        self.assertRecordValues(report.contribution_line_ids, [{
            'ermc': 1010.0,
        }, {
            'ermc': 1010.0,
        }, {
            'ermc': 1010.0,
        }])

    def _create_payrun_and_report(self, date_start, date_end, validate_report=True):
        payslip_run = self.env['hr.payslip.run'].create({
            'name': "Test Payslip Run",
            'date_start': date_start,
            'date_end': date_end,
            'structure_id': self.env.ref('l10n_hk_hr_payroll.hr_payroll_structure_cap57_employee_salary').id,
            'l10n_hk_payroll_scheme_id': self.mpf_scheme.id,
        })
        payslip_run.generate_payslips(payslip_run._get_valid_version_ids())
        payslip_run.action_validate()

        report = payslip_run.l10n_hk_payroll_empf_report_id
        if validate_report:
            report.action_validate()
        return report

    def _get_csv_reports_per_type(self, report, report_type=None):
        """
        Helper to get csv for each type of report for the given report.
        Optionally, the report type can be provided if only this specific type is tested, in which case we return the
        attachment corresponding to this type right away.
        """
        existing_csv_reports = self.env["ir.attachment"].search(
            [
                ("res_id", "=", report.id),
                ("res_model", "=", "l10n_hk.empf.contribution.report"),
            ]
        )
        csv_reports_per_type = {
           'new_employees': None,
           'contributions': None,
           'terminated_employees': None,
        }
        for csv_report in existing_csv_reports:
            for label in csv_reports_per_type:
                if label in csv_report.name:
                    csv_reports_per_type[label] = csv_report

        return csv_reports_per_type[report_type] if report_type else csv_reports_per_type
