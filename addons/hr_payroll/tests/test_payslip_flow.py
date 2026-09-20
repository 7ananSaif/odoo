# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from dateutil.relativedelta import relativedelta
from odoo import Command
from odoo.tests import HttpCase, tagged
from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import UserError
from odoo.tests import Form


class TestPayslipFlow(TestPayslipBase):

    def test_00_payslip_flow(self):
        """ Testing payslip flow and report printing """

        # I create an employee Payslip
        richard_payslip = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': self.richard_emp.id,
        })

        payslip_input = self.env['hr.payslip.input'].search([('payslip_id', '=', richard_payslip.id)])
        # I assign the amount to Input data
        payslip_input.write({'amount': 5.0})

        # I verify the payslip is in draft state
        self.assertEqual(richard_payslip.state, 'draft', 'State not changed!')

        richard_payslip.compute_sheet()

        # Then I click on the 'Confirm' button on payslip
        richard_payslip.action_payslip_done()

        # I verify that the payslip is in validated state
        self.assertEqual(richard_payslip.state, 'validated', 'State not changed!')

        # Then I click on the 'Mark as paid' button on payslip
        richard_payslip.action_payslip_paid()

        # I verify that the payslip is in paid state
        self.assertEqual(richard_payslip.state, 'paid', 'State not changed!')

        # I want to check refund payslip so I click on refund button.
        richard_payslip.refund_sheet()

        # I check on new payslip Credit Note is checked or not.
        payslip_refund = self.env['hr.payslip'].search([('name', 'like', 'Refund: '+ richard_payslip.name), ('credit_note', '=', True)])
        self.assertTrue(bool(payslip_refund), "Payslip not refunded!")

        # I want to generate a payslip from Payslip run.
        payslip_run = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee'
        })

        # I create record for generating the payslip for this Payslip run.

        # The contract of Richard starts in 2018, the payrun is for 2011, no valid versions can be found.
        # So the generate_payslip without versions must raise an error
        with self.assertRaises(UserError):
            payslip_run.generate_payslips(employee_ids=[self.richard_emp.id])

    def test_01_batch_with_specific_structure(self):
        """ Generate payslips for the employee whose running contract is based on the same Salary Structure Type"""

        specific_structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Structure Type Test'
        })

        specific_structure = self.env['hr.payroll.structure'].create({
            'name': 'End of the Year Bonus - Test',
            'type_id': specific_structure_type.id,
        })

        # 13th month pay
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'structure_id': specific_structure.id,
            'name': 'End of the year bonus',
        })

        with self.assertRaises(UserError):
            payslip_run.generate_payslips(payslip_run._get_valid_version_ids())

        # Update the structure type and generate payslips again
        specific_structure_type.default_struct_id = specific_structure.id
        self.richard_emp.version_ids[0].structure_type_id = specific_structure_type.id

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'structure_id': specific_structure.id,
            'name': 'Batch for Structure',
        })

        payslip_run.generate_payslips(payslip_run._get_valid_version_ids())

        self.richard_emp.structure_type_id = specific_structure_type.id

        self.assertTrue(payslip_run.slip_ids)
        self.assertTrue(self.richard_emp.id in payslip_run.slip_ids.employee_id.ids)

        self.assertEqual(len(payslip_run.slip_ids), 1)
        self.assertEqual(payslip_run.slip_ids.struct_id.id, specific_structure.id)

    def test_02_payslip_batch_with_archived_employee(self):
        # archive his contact
        self.richard_emp.action_archive()

        # 13th month pay
        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'End of the year bonus'
        })
        # I create record for generating the payslip for this Payslip run.
        payslip_run.generate_payslips(employee_ids=[self.richard_emp.id])

        self.assertEqual(len(payslip_run.slip_ids), 1)

    def test_03_payslip_batch_with_payment_process(self):
        '''
            Test to check if some payslips in the batch are already paid,
            the batch status can be updated to 'paid' without affecting
            those already paid payslips.
        '''
        self.contract_jules = self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
            'structure_type_id': self.structure_type.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
        })

        payslip_run.generate_payslips(employee_ids=[self.richard_emp.id, self.jules_emp.id])

        payslip_run.action_validate()

        self.assertEqual(len(payslip_run.slip_ids), 2)
        self.assertTrue(all(payslip.state == 'validated' for payslip in payslip_run.slip_ids), 'State not changed!')

        # Mark the first payslip as paid and store the paid date
        payslip_run.slip_ids[0].action_payslip_paid()
        paid_date = payslip_run.slip_ids[0].paid_date

        self.assertEqual(payslip_run.slip_ids[0].state, 'paid', 'State not changed!')
        self.assertEqual(payslip_run.slip_ids[1].state, 'validated', 'State not changed!')

        payslip_run.action_paid()

        self.assertEqual(payslip_run.state, '03_paid', 'State not changed!')
        self.assertTrue(all(payslip.state == 'paid' for payslip in payslip_run.slip_ids), 'State not changed!')
        self.assertEqual(payslip_run.slip_ids[0].paid_date, paid_date, 'payslip paid date should not be changed')

    def test_04_payslip_batch_wizard_for_employee_selection_mode(self):
        '''
            Test employee_ids selection in batch payslip generating wizard
            based on employee selection mode fields
        '''
        self.richard_emp.version_ids[0].contract_date_end = False
        self.contract_jules = self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
        })

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
        })

        payslip_run.generate_payslips(employee_ids=[self.richard_emp.id, self.jules_emp.id])

        self.assertEqual(len(payslip_run.slip_ids.employee_id.ids), 2)
        self.assertTrue(all(employee in [self.richard_emp.id, self.jules_emp.id] for employee in payslip_run.slip_ids.employee_id.ids))

    def test_05_payslip_batch_wizard_for_department_selection_mode(self):
        '''
            Test employee_ids selection in batch payslip generating wizard
            based on department selection mode fields
        '''
        self.richard_emp.version_ids[0].date_end = False
        self.contract_jules = self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
        })
        self.richard_emp.department_id = False

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
        })

        employees = self.env["hr.employee"].search([('department_id', 'in', [self.dep_rd.id])])

        payslip_run.generate_payslips(employee_ids=employees.ids)

        self.assertEqual(len(employees.ids), 1)
        self.assertEqual(employees.ids[0], self.jules_emp.id)

    def test_06_payslip_batch_wizard_for_job_selection_mode(self):
        '''
            Test employee_ids selection in batch payslip generating wizard
            based on job selection mode fields
        '''
        self.richard_emp.version_ids[0].date_end = False
        job_developer = self.env['hr.job'].create({
            'name': 'Experienced Developer',
            'department_id': self.dep_rd.id,
            'no_of_recruitment': 5,
        })
        self.richard_emp.job_id = job_developer.id

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
        })

        employees = self.env["hr.employee"].search([('job_id', 'in', [job_developer.id])])

        payslip_run.generate_payslips(employee_ids=employees.ids)

        self.assertEqual(len(employees.ids), 1)
        self.assertTrue(self.richard_emp in employees)

    def test_07_payslip_batch_wizard_for_category_selection_mode(self):
        '''
            Test employee_ids selection in batch payslip generating wizard
            based on category selection mode fields
        '''
        self.richard_emp.version_ids[0].date_end = False
        self.contract_jules = self.jules_emp.version_id.write({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'name': 'Contract for Jules',
            'wage': 5000.33,
            'employee_id': self.jules_emp.id,
        })
        category_tag = self.env['hr.employee.category'].create({'name': 'Test category'})
        self.jules_emp.category_ids = [category_tag.id]

        payslip_run = self.env['hr.payslip.run'].create({
            'date_start': datetime.date.today() + relativedelta(years=-1, month=8, day=1),
            'date_end': datetime.date.today() + relativedelta(years=-1, month=8, day=31),
            'name': 'Payment Test',
        })

        employees = self.env["hr.employee"].search([('category_ids', 'in', [category_tag.id])])

        payslip_run.generate_payslips(employee_ids=employees.ids)

        self.assertEqual(len(employees.ids), 1)
        self.assertEqual(employees.ids[0], self.jules_emp.id)

    def test_08_payslip_batch_wizard_for_structure_type_selection_mode_with_multiple_contract(self):
        structure_typeA, structure_typeB = self.env['hr.payroll.structure.type'].create([
            {'name': 'Test A'},
            {'name': 'Test B'},
        ])

        structureA, structureB = self.env['hr.payroll.structure'].create([
            {
                'name': 'Test structure A',
                'type_id': structure_typeA.id,
            },
            {
                'name': 'Test structure B',
                'type_id': structure_typeB.id,
            },
        ])

        payslip_runA, payslip_runB, payslip_runC = self.env['hr.payslip.run'].create([
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=2, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=2, day=31),
                'structure_id': structureA.id,
                'name': 'Payslip RUN A'
            },
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=4, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=4, day=31),
                'structure_id': structureB.id,
                'name': 'Payslip RUN B'
            },
            {
                'date_start': datetime.date.today() + relativedelta(years=-1, month=3, day=1),
                'date_end': datetime.date.today() + relativedelta(years=-1, month=3, day=31),
                'structure_id': structureB.id,
                'name': 'Payslip RUN C'
            },
        ])

        employee_timmy, employee_gerard, employee_michel = self.env['hr.employee'].create([
            {
                'name': 'Timmy',
                'sex': 'male',
                'birthday': '1984-05-01',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_end': datetime.date.today() + relativedelta(years=-1, month=3, day=15),
                'wage': 5000.33,
                'structure_type_id': structure_typeA.id,
            },
            {
                'name': 'Gerard',
                'sex': 'male',
                'birthday': '1964-01-23',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'wage': 5000.33,
                'structure_type_id': structure_typeA.id,
            },
            {
                'name': 'Michel',
                'sex': 'male',
                'birthday': '1975-10-06',
                'date_version': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=1, day=1),
                'wage': 7000.33,
                'structure_type_id': structure_typeB.id,
            },
        ])

        employee_timmy.create_version({
            'date_version': datetime.date.today() + relativedelta(years=-1, month=3, day=16),
            'contract_date_start': datetime.date.today() + relativedelta(years=-1, month=3, day=16),
            'contract_date_end': datetime.date.today() + relativedelta(years=1, month=3, day=31),
            'wage': 7000.33,
            'employee_id': employee_timmy.id,
            'structure_type_id': structure_typeB.id,
        })

        # Batch A for only structure A
        # For february YEAR-1
        # Expected employees/contracts
        # Timmy  contract A (YEAR-1/01/01 -> YEAR-1/03/15)
        # Gerard contract A (YEAR-1/01/01 -> no end date )
        payslip_runA.generate_payslips(payslip_runA._get_valid_version_ids())
        self.assertEqual(len(payslip_runA.slip_ids.employee_id.ids), 2)
        self.assertEqual(len(payslip_runA.slip_ids.ids), 2)
        self.assertTrue(all(
            payslip.version_id.structure_type_id == payslip.struct_id.type_id and
            payslip.struct_id.type_id == payslip_runA.structure_id.type_id
        for payslip in payslip_runA.slip_ids))

        # Batch B for only structure B
        # For april YEAR-1
        # Expected employees/contracts
        # Timmy  contract B (YEAR-1/03/16 -> no end date)
        # Michel contract B (YEAR-1/01/01 -> no end date)
        payslip_runB.generate_payslips(payslip_runB._get_valid_version_ids())
        self.assertEqual(len(payslip_runB.slip_ids.employee_id.ids), 2)
        self.assertEqual(len(payslip_runB.slip_ids.ids), 2)
        self.assertTrue(all(
            payslip.version_id.structure_type_id == payslip.struct_id.type_id and
            payslip.struct_id.type_id == payslip_runB.structure_id.type_id
        for payslip in payslip_runB.slip_ids))

        # Batch C for two structures
        # For march YEAR-1
        # Expected employees/contracts
        # Timmy| contract A (YEAR-1/01/01 -> YEAR-1/03/15)
        #      | contract B (YEAR-1/03/16 -> no end date )
        # Gerard contract A (YEAR-1/01/01 -> no end date )
        # Michel contract B (YEAR-1/01/01 -> no end date )
        payslip_runC.generate_payslips(payslip_runC._get_valid_version_ids())
        self.assertEqual(len(payslip_runC.slip_ids.employee_id.ids), 2)
        self.assertEqual(len(payslip_runC.slip_ids.ids), 2)
        self.assertTrue(all(
            payslip.version_id.structure_type_id == payslip.struct_id.type_id and
            payslip.struct_id.type_id == payslip_runC.structure_id.type_id
        for payslip in payslip_runC.slip_ids))

    def test_09_payslip_creation_with_employee_without_contract(self):
        employee = self.env['hr.employee'].create({
            'name': 'Johnny',
        })
        payslip_form = Form(self.env['hr.payslip'])
        payslip_form.employee_id = employee
        payslip_form.save()
        self.assertTrue(payslip_form)

    def test_10_related_payslip_not_flagged_as_duplicate(self):
        """Refund/Correction payslips must NOT be treated as duplicates."""

        original = self.env['hr.payslip'].create({
            'name': 'Original Payslip',
            'employee_id': self.richard_emp.id,
            'struct_id': self.richard_emp.structure_type_id.default_struct_id.id,
            'date_from': datetime.date(2025, 12, 1),
            'date_to': datetime.date(2025, 12, 31),
        })
        original.compute_sheet()
        original.action_payslip_done()
        original.correct_sheet()
        related = original.related_payslip_ids
        refund = related.filtered(lambda p: p.is_refund_payslip)
        correction = related - refund

        warnings = refund._get_warnings_by_slip()[refund]
        self.assertFalse(
            any("Similar payslips found" in (w.get('message') or "") for w in warnings),
            "Refund payslip incorrectly flagged as duplicate."
        )

        correction_warnings = correction._get_warnings_by_slip()[correction]
        self.assertFalse(
            any("Similar payslips found" in (w.get('message') or "") for w in correction_warnings),
            "Correction payslip incorrectly flagged as duplicate."
        )

        duplicate = self.env['hr.payslip'].create({
            'name': 'Actual Duplicate Payslip',
            'employee_id': self.richard_emp.id,
            'struct_id': original.struct_id.id,
            'date_from': original.date_from,
            'date_to': original.date_to,
        })
        duplicate_warnings = duplicate._get_warnings_by_slip()[duplicate]
        self.assertTrue(
            any("Similar payslips found" in (w.get('message') or "") for w in duplicate_warnings),
            "Unrelated duplicate payslip should still trigger the warning."
        )

    def test_04_cancel_a_done_payslip_with_payroll_admin(self):
        """Cancel a validated payslip using a new user with Payroll Admin access."""
        test_user = mail_new_test_user(
            self.env, name="Test user", login="test_user",
            groups="hr_payroll.group_hr_payroll_manager"
        )
        richard_payslip = self.env['hr.payslip'].create({
            'name': 'Payslip of Richard',
            'employee_id': self.richard_emp.id,
        })
        richard_payslip.action_payslip_done()
        self.assertEqual(richard_payslip.state, 'validated')
        richard_payslip.with_user(test_user).action_payslip_cancel()
        self.assertEqual(richard_payslip.state, 'cancel')

    def test_hr_payslip_without_date_to(self):
        """Ensure payslip creation fails if date_to is missing."""
        employee = self.env['hr.employee'].create({
            'name': 'Jethalal Gada',
            'date_version': '2025-10-01',
            'contract_date_start': '2025-10-01',
        })

        payslip_form = Form(self.env['hr.payslip'])
        payslip_form.employee_id = employee
        payslip_form.date_to = False
        with self.assertRaises(AssertionError):
            payslip_form.save()
        self.assertTrue(payslip_form)

    def test_05_fully_flexible_contracts_payslip(self):
        """ Test payslip generation for fully flexible contracts (no working schedule) with attendance-based work entries """

        if not self.env["ir.module.module"].search([("name", "=", "hr_work_entry_attendance"), ("state", "=", "installed")]):
            self.skipTest("Module 'hr_work_entry_attendance' is not installed!")

        attendance_work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance')

        # Case 1: contract with no calendar
        date_from = datetime.date.today()
        date_to = date_from + relativedelta(months=1)

        employee_with_calendar = self.env['hr.employee'].create({
            'name': 'employee 1',
            'resource_calendar_id': self.env.ref('resource.resource_calendar_std').id,
            'work_entry_source': 'attendance',
            'wage': 5000,
            'structure_type_id': self.structure_type.id,
            'date_version': date_from - relativedelta(months=2),
            'contract_date_start': date_from - relativedelta(months=2),
        })

        flexible_contract_1 = employee_with_calendar.version_id
        flexible_contract_1.resource_calendar_id = False

        for day in range(7):
            work_date = date_from + relativedelta(days=day)
            if work_date.weekday() < 5:
                self.env['hr.work.entry'].create({
                    'name': f'attendance {day + 1}',
                    'employee_id': employee_with_calendar.id,
                    'version_id': flexible_contract_1.id,
                    'work_entry_type_id': attendance_work_entry_type.id,
                    'date': work_date,
                    'duration': 8,
                })

        payslip_1 = self.env['hr.payslip'].create({
            'name': "payslip of employee 1",
            'employee_id': employee_with_calendar.id,
            'date_from': date_from,
            'date_to': date_to,
        })

        payslip_1.compute_sheet()

        self.assertTrue(payslip_1.worked_days_line_ids, 'worked days should be generated for fully flexible contract')
        attendance_line_1 = payslip_1.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == attendance_work_entry_type)
        self.assertTrue(attendance_line_1, 'attendance worked days should be present')
        self.assertEqual(attendance_line_1.number_of_days, 5, 'payslip should record 5 worked days')
        self.assertEqual(attendance_line_1.number_of_hours, 40, 'payslip should record 40 hours')

        # Case 2: employee with no calendar, contract with no calendar (full flexibility in both)
        employee_no_calendar = self.env['hr.employee'].create({
            'name': 'employee 2',
            'resource_calendar_id': False,
            'work_entry_source': 'attendance',
            'wage': 6000,
            'structure_type_id': self.structure_type.id,
            'date_version': date_from - relativedelta(months=2),
            'contract_date_start': date_from - relativedelta(months=2),
        })

        flexible_contract_2 = employee_no_calendar.version_id

        for day in range(7):
            work_date = date_from + relativedelta(days=day + 10)
            if work_date.weekday() < 5:
                self.env['hr.work.entry'].create({
                    'name': f'Attendance {day + 1}',
                    'employee_id': employee_no_calendar.id,
                    'version_id': flexible_contract_2.id,
                    'work_entry_type_id': attendance_work_entry_type.id,
                    'date': work_date,
                    'duration': 8,
                })

        payslip_2 = self.env['hr.payslip'].create({
            'name': 'payslip 2',
            'employee_id': employee_no_calendar.id,
            'date_from': date_from,
            'date_to': date_to,
        })

        payslip_2.compute_sheet()

        self.assertTrue(payslip_2.worked_days_line_ids, 'worked days should be generated for fully flexible contract')
        attendance_line_2 = payslip_2.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id == attendance_work_entry_type)
        self.assertTrue(attendance_line_2, 'attendance worked days should be present')
        self.assertGreater(attendance_line_2.number_of_hours, 0, 'payslip record attendance hours')

    def test_06_pay_run_payslip_name(self):
        """
        This test checks that the name of the payslip contains the name and the period for which the pay run is
        being run.
        """
        payslip_run = self.env['hr.payslip.run'].create({
            'date_end': '2025-11-30',
            'date_start': '2025-11-01',
            'name': 'Payslip for Employee'
        })
        payslip_run.generate_payslips(employee_ids=[self.richard_emp.id])
        self.assertEqual(payslip_run.slip_ids.name, 'Salary Slip - Richard - November 2025')


@tagged('-at_install', 'post_install')
class TestPayslipUi(HttpCase):
    def test_tour_date_input(self):
        """Test payslip form date input."""
        self.start_tour("/odoo", 'hr_payroll_form_view_date_input_tour', login='admin')
