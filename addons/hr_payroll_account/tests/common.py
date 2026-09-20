# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from odoo.tools import float_compare


@tagged('post_install', 'post_install_l10n', '-at_install', 'payslips_validation')
class TestPayslipValidationCommon(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('hr_payroll.group_hr_payroll_user')

    @classmethod
    def _setup_common(cls, country, structure, structure_type, resource_calendar=False, car=False, contract_fields=False, employee_fields=False, tz=False):
        """
        This method setups a set of common models that will be used to test payslip validation.

        It will create a partner and an employee that are in the company in cls.env.company.
        The employee and company resource calendar will be a standard full-time 40h/week calendar.
        The default timezone is 'America/Los_Angeles'.

        It will also create a contract for the employee in the same company with:
            - a default start date at the 1st of January 2016
            - a default wage amounting to 1000.0 of whatever the currency of the company is.

        In the following parameter descriptions, 'xx' is the standard 2-letter country code.
        :param country: Record of the country (usually base.xx)
        :param structure: Record of the default structure (usually l10n_xx_hr_payroll.hr_payroll_structure_xx_employee_salary)
        :param structure_type: Record of the default structure type (usually l10n_xx_hr_payroll.structure_type_employee_xx)
        :param resource_calendar: Record of a resource calendar if you want to replace the default one
        :param car: Record of the employee's fleet car, False by default
        :param contract_fields: Dict of field names: value, that will be overridden on the contract created
        :param employee_fields: Dict of field names: value, that will be overridden on the employee created
        :param tz: String of a timezone that is set for both the user and the resource calendar
        :return:
        """
        cls.country = country
        country_code = country.code.upper()

        cls.structure = structure

        cls.tz = tz or 'America/Los_Angeles'
        cls.env.user.tz = cls.tz

        cls.work_contact = cls.env['res.partner'].create({
            'name': country_code + ' Employee',
            'company_id': cls.env.company.id,
        })
        cls.resource_calendar = resource_calendar or cls.env['resource.calendar'].sudo().create([{
            'name': "Standard Calendar : 40 Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': 8.0,
            'tz': cls.tz,
            'two_weeks_calendar': False,
            'hours_per_week': 40.0,
            'full_time_required_hours': 40.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'name': "Attendance",
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'day_period': day_period,
                'work_entry_type_id': cls.env.ref('hr_work_entry.work_entry_type_attendance').id
            }) for dayofweek, hour_from, hour_to, day_period in [
                ("0", 8.0, 12.0, "morning"),
                ("0", 12.0, 13.0, "lunch"),
                ("0", 13.0, 17.0, "afternoon"),
                ("1", 8.0, 12.0, "morning"),
                ("1", 12.0, 13.0, "lunch"),
                ("1", 13.0, 17.0, "afternoon"),
                ("2", 8.0, 12.0, "morning"),
                ("2", 12.0, 13.0, "lunch"),
                ("2", 13.0, 17.0, "afternoon"),
                ("3", 8.0, 12.0, "morning"),
                ("3", 12.0, 13.0, "lunch"),
                ("3", 13.0, 17.0, "afternoon"),
                ("4", 8.0, 12.0, "morning"),
                ("4", 12.0, 13.0, "lunch"),
                ("4", 13.0, 17.0, "afternoon"),
            ]],
        }]).sudo(False)
        cls.env.company.write({
            'resource_calendar_id': cls.resource_calendar.id,
        })

        cls.employee = cls.env['hr.employee'].sudo().create({
            'name': country_code + ' Employee',
            'work_contact_id': cls.work_contact.id,
            'address_id': cls.work_contact.id,
            'resource_calendar_id': cls.resource_calendar.id,
            'company_id': cls.env.company.id,
            'country_id': country.id,
            'structure_type_id': structure_type.id,
            'contract_date_start': date(2016, 1, 1),
            'date_version': date(2016, 1, 1),
            'wage': 1000.0,
            **(employee_fields or {})
        }).sudo(False)

        contract = cls.employee.sudo().version_id
        if contract_fields:
            contract.write(contract_fields)
        cls.contract = contract.sudo(False)

        cls.car = car
        if cls.car:
            cls.car.sudo().write({'driver_id': cls.employee.work_contact_id.id})
            # This field only exists if fleet is installed
            cls.contract.sudo().write({'car_id': cls.car.id})

    @classmethod
    def _generate_payslip(cls, date_from, date_to, struct_id=False, input_line_ids=False, version_id=False, employee_id=False):
        work_entries = cls.contract.generate_work_entries(date_from, date_to)
        payslip = cls.env['hr.payslip'].create([{
            'name': "Test Payslip",
            'employee_id': employee_id or cls.employee.id,
            'version_id': version_id or cls.contract.id,
            'company_id': cls.env.company.id,
            'struct_id': struct_id or cls.structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'input_line_ids': input_line_ids or [],
        }])
        # This field only exists if fleet is installed
        if cls.car:
            payslip.write({'vehicle_id': cls.car.id})
        work_entries.action_validate()
        payslip.compute_sheet()
        return payslip

    @classmethod
    def _generate_leave(cls, date_from, date_to, holiday_status_id):
        leave = cls.env['hr.leave'].sudo().create({
            'employee_id': cls.employee.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'holiday_status_id': holiday_status_id.id,
        })

        if holiday_status_id.leave_validation_type != 'no_validation':
            leave.action_approve()

    def _validate_payslip(self, payslip, results, skip_lines=False):
        error = []
        payslip_lines = payslip.line_ids.filtered(lambda l: not l.salary_rule_id.title)
        line_values = payslip._get_line_values(set(payslip_lines.mapped('code')))
        for code, value in results.items():
            if code in line_values:
                payslip_line_value = line_values[code][payslip.id]['total']
                if float_compare(payslip_line_value, value, 2):
                    error.append(f"{'WRONG CALCULATION':>20} │ {code:<30} │ {value:>15} │ {payslip_line_value:>15} │ {round(payslip_line_value-value, 2):>15} │")
        if not skip_lines:
            for code, value in results.items():
                if code not in payslip_lines.mapped('code'):
                    error.append(
                        f"{'UNNECESSARY LINE':>20} │ {code:<30} │ {value:>15} │ {'/':>15} │")
            for line in payslip_lines:
                if line.code not in results:
                    error.append(
                        f"{'MISSING LINE':>20} │ {line.code:<30} │ {'/':>15} │ {line_values[line.code][payslip.id]['total']:>15} │")
        if error:
            error.insert(
                0,
                f"{'ERROR':>20} │ {'CODE':<30} │ {'EXPECTED':>15} │ {'REALITY':>15} │ {'DIFFERENCE':>15} │\n"
                f"{'':>20} │ {'':<30} │ {'':>15} │ {'':>15} │ {'':>15} │")
            error.extend([
                "",
                f"Payslip Period: {payslip.date_from} - {payslip.date_to}",
                "Payslip Actual Values: ",
                "        payslip_results = {" + ', '.join(f"'{line.code}': {line_values[line.code][payslip.id]['total']}" for line in payslip_lines) + "}"
            ])
        self.assertEqual(len(error), 0, '\n\n' + '\n'.join(error))

    def _validate_worked_days(self, payslip, results, skip_lines=False):
        """
        Validate the worked days lines of a payslip.
        :param payslip: The payslip
        :param results: A dict of {work_entry_code: (number_of_days, number_of_hours, amount)}
        :param skip_lines: If True, we don't check that all lines are present in the payslip
        :return:
        """
        error = []
        line_values = payslip._get_worked_days_line_values(set(results.keys()) | set(payslip.worked_days_line_ids.mapped('code')), ['number_of_days', 'number_of_hours', 'amount'])
        for code, (number_of_days, number_of_hours, amount) in results.items():
            payslip_line_value = line_values[code][payslip.id]['number_of_days']
            if float_compare(payslip_line_value, number_of_days, 2):
                error.append("Code: %s - Expected Number of Days: %s - Reality: %s" % (code, number_of_days, payslip_line_value))
            payslip_line_value = line_values[code][payslip.id]['number_of_hours']
            if float_compare(payslip_line_value, number_of_hours, 2):
                error.append("Code: %s - Expected Number of Hours: %s - Reality: %s" % (code, number_of_hours, payslip_line_value))
            payslip_line_value = line_values[code][payslip.id]['amount']
            if float_compare(payslip_line_value, amount, 2):
                error.append("Code: %s - Expected Amount: %s - Reality: %s" % (code, amount, payslip_line_value))
        if not skip_lines:
            for line in payslip.worked_days_line_ids:
                if line.code not in results:
                    error.append("Missing Line: '%s' - %s Days - %s Hours - %s CHF," % (
                        line.code,
                        line_values[line.code][payslip.id]['number_of_days'],
                        line_values[line.code][payslip.id]['number_of_hours'],
                        line_values[line.code][payslip.id]['amount'],
                    ))
        if error:
            error.extend([
                f"Payslip Period: {payslip.date_from} - {payslip.date_to}",
                "Payslip Actual Values: ",
                "        {"
            ])
            for line in payslip.worked_days_line_ids:
                error.append("            '%s': (%s, %s, %s)," % (
                    line.code,
                    line_values[line.code][payslip.id]['number_of_days'],
                    line_values[line.code][payslip.id]['number_of_hours'],
                    line_values[line.code][payslip.id]['amount'],
                ))
            error.append("        }")
        self.assertEqual(len(error), 0, '\n' + '\n'.join(error))

    def _validate_move_lines(self, lines, results):
        error = []
        for code, move_type, amount in results:
            if not any(l.account_id.code == code and not float_compare(l[move_type], amount, 2) for l in lines):
                error.append("Couldn't find %s move line on account %s with amount %s" % (move_type, code, amount))
        if error:
            for line in lines:
                for move_type in ['credit', 'debit']:
                    if line[move_type]:
                        error.append('%s - %s - %s' % (line.account_id.code, move_type, line[move_type]))
        self.assertEqual(len(error), 0, '\n' + '\n'.join(error))

    def _add_other_input(self, payslip_id, other_input_id, amount):
        self.env['hr.payslip.input'].create({
            'payslip_id': payslip_id.id,
            'input_type_id': other_input_id.id,
            'amount': amount,
        })

    def _add_rule_parameter_value(self, rule_parameter_code, value, date):
        rule_parameter_id = self.env['hr.rule.parameter'].search([('code', '=', rule_parameter_code)]).id
        value_on_same_date = self.env['hr.rule.parameter.value'].search([
            ('rule_parameter_id', '=', rule_parameter_id),
            ('date_from', '=', date)
        ])
        if value_on_same_date:
            value_on_same_date.sudo().write({'parameter_value': value})
        else:
            self.env['hr.rule.parameter.value'].sudo().create({
                'rule_parameter_id': rule_parameter_id,
                'parameter_value': value,
                'date_from': date,
            })
