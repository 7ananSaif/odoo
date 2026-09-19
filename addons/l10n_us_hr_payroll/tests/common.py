# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import fields, Command
from odoo.tests import TransactionCase


class CommonTestPayslips(TransactionCase):
    @classmethod
    def create_payslip_run(cls):
        def create_employee_with_bank_account(employee_name):
            employee_id = cls.env['hr.employee'].create({
                'name': employee_name
            })
            # Create employee bank account
            bank_account = cls.env["res.partner.bank"].create({
                "partner_id": employee_id.work_contact_id.id,
                "acc_number": "GB94BARC10201530093459",
                "clearing_number": "123456780",
                'allow_out_payment': True,
            })
            employee_id.bank_account_ids = [Command.link(bank_account.id)]
            return employee_id

        def create_contract(contract_name, wage, start, employee):
            employee.version_id.write({
                'name': contract_name,
                'wage': wage,
                'contract_date_start': start,
                'date_version': start,
            })
            return employee.version_id

        def create_employees_with_contracts(no_employees):
            employees = cls.env['hr.employee']
            versions = cls.env['hr.version']
            contract_start_date = fields.Date.start_of(fields.Date.today(), "year")
            for i in range(1, no_employees + 1):
                employee = create_employee_with_bank_account('employee_' + str(i))
                version = create_contract('contract_' + str(i), i * 2000, contract_start_date, employee)
                employees |= employee
                versions |= version
            return employees

        def create_and_compute_payslip_run(employee_ids):
            payslip_date = fields.Date.today() + relativedelta(day=1)
            payslip_run_id = cls.env['hr.payslip.run'].create({
                'name': 'Payslip Run',
                'date_start': payslip_date
            })
            for employee_id in employee_ids:
                # Create the employee's payslip and link it to the payslip_run_id
                payslip_id = cls.env['hr.payslip'].create({
                    'name': employee_id.name + '_payslip',
                    'employee_id': employee_id.id,
                    'payslip_run_id': payslip_run_id.id,
                    'struct_id': cls.env.ref('hr_payroll.default_structure', False).id,
                    "date_from": payslip_date,
                })
                payslip_id.compute_sheet()
            return payslip_run_id

        employees = create_employees_with_contracts(no_employees=2)
        return create_and_compute_payslip_run(employees)
