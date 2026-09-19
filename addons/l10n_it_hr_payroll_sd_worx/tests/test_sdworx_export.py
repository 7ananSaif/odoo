# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import date

from odoo.tests import tagged
from odoo.exceptions import UserError

from .common import TestSdworxITExportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSdworxITExportLogic(TestSdworxITExportCommon):

    def _generate_and_get_content(self, employees, month, year):
        export_form = self.env['l10n.it.hr.payroll.export.sdworx'].create({
            'reference_month': str(month),
            'reference_year': str(year),
            'company_id': self.it_company.id,
        })

        start_date = export_form.period_start
        end_date = export_form.period_stop
        employees.generate_work_entries(start_date, end_date)
        contracts_by_employee = export_form._get_contracts_by_employee(employee_ids=employees.ids)
        create_lines = []
        for emp in employees:
            if emp in contracts_by_employee:
                create_lines.append((0, 0, {
                    'employee_id': emp.id,
                    'version_ids': [(6, 0, contracts_by_employee[emp].ids)]
                }))
        export_form.write({
            'eligible_employee_line_ids': [(5, 0, 0)] + create_lines
            })
        export_form.action_export_file()
        self.assertTrue(export_form.export_file, "The export file should have been generated.")
        return base64.b64decode(export_form.export_file).decode('utf-8')

    def test_missing_company_or_employee_code_errors(self):
        """
        - No company code -> UserError
        - Employee without code -> UserError
        """
        old_company_code = self.it_company.official_company_code
        self.it_company.official_company_code = False
        export_form = self.env['l10n.it.hr.payroll.export.sdworx'].with_company(self.it_company).create({
            'reference_month': '7',
            'reference_year': '2025',
            'eligible_employee_line_ids': [(0, 0, {
                'employee_id': self.richard_emp.id,
                'version_ids': [(6, 0, self.richard_emp.version_ids.ids)],
            })],
        })
        with self.assertRaises(UserError, msg='There is no SDWorx code defined on the company. Please configure it on the Payroll Settings'):
            export_form.action_export_file()

        self.it_company.official_company_code = old_company_code
        self.richard_emp.l10n_it_sdworx_code = False
        with self.assertRaises(UserError, msg='There is no SDWorx code defined for the following employees:\n Richard Doe'):
            export_form.action_export_file()

    def test_export_full_day_leave(self):
        if self.env.ref('base.module_hr_holidays').state != 'installed':
            return
        leave_date = date(2025, 6, 9)
        leave = self.env['hr.leave'].with_company(self.it_company).create({
            'name': 'Full Day Leave Test',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type_day_it.id,
            'request_date_from': leave_date,
            'request_date_to': leave_date,
        })
        leave._action_validate()
        xml_text = self._generate_and_get_content(self.richard_emp, 6, 2025)

        self.assertIn(
            "<Movimento>\n        <CodGiustificativoRilPres>FER</CodGiustificativoRilPres>\n        <CodGiustificativoUfficiale>FER</CodGiustificativoUfficiale>\n        <Data>2025-06-09</Data>\n        <NumOre>8</NumOre>\n      </Movimento>\n",
            xml_text,
        )
        self.assertNotIn(
            "<Data>2025-06-09</Data>\n        <CodGiustificativoRilPres>01</CodGiustificativoRilPres>",
            xml_text,
        )

    def test_export_half_day_leave(self):
        if self.env.ref('base.module_hr_holidays').state != 'installed':
            return
        leave_date = date(2025, 6, 9)
        leave = self.env['hr.leave'].with_company(self.it_company).create({
            'name': 'Half Day Leave Test',
            'employee_id': self.richard_emp.id,
            'holiday_status_id': self.leave_type_half_day.id,
            'request_date_from': leave_date,
            'request_date_to': leave_date,
            'request_unit_half': True,
            'request_date_from_period': 'pm',
        })
        leave._action_validate()
        xml_text = self._generate_and_get_content(self.richard_emp, 6, 2025)

        self.assertIn(
            "<Movimento>\n        <CodGiustificativoRilPres>FER</CodGiustificativoRilPres>\n        <CodGiustificativoUfficiale>FER</CodGiustificativoUfficiale>\n        <Data>2025-06-09</Data>\n        <NumOre>4</NumOre>\n      </Movimento>\n",
            xml_text,
        )
        self.assertIn(
            "<Movimento>\n        <CodGiustificativoRilPres>01</CodGiustificativoRilPres>\n        <CodGiustificativoUfficiale>01</CodGiustificativoUfficiale>\n        <Data>2025-06-09</Data>\n        <NumOre>4</NumOre>\n      </Movimento>\n",
            xml_text,
        )
