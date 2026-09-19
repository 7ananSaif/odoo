# Part of Odoo. See LICENSE file for full copyright and licensing details
from odoo import fields

from .common import TestPlanningContractCommon


class TestPlanningGanttResourceEmployeeWorkingPeriods(TestPlanningContractCommon):
    """
        Currently gantt_resource_employees_working_periods method supplies data to Gantt Model.
        The goal is check if the method correctly filters contracts.
        Test Goals -
        1). Contract in State "draft" is only chosen if its kanban_state is in "done"
        2). Contracts in States "open" and "close" are chosen regardless of the kanban_state
        3). Any other type of combination is not accepted and takes its working period as default scale time
        Here the context dates refer to dates we from gantt view through the RPC request sent. These refer to
        start date and end dates of the scale. If the scale is week, the starting date of week is default_start_datetime
        and end date if weeek is default_end_datetime.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = 'UTC'

        cls.contract_start_date = "2024-08-15 00:00:00"
        cls.contract_end_date = "2024-08-16 23:59:59"

        cls.context_dates_inside_contracts = {
            "default_start_datetime": "2024-08-11 10:00:00",
            "default_end_datetime": "2024-08-17 19:00:00",
        }
        cls.context_dates_outside_contract = {
            "default_start_datetime": "2024-08-18 10:00:00",
            "default_end_datetime": "2024-08-24 19:00:00",
        }

        cls.employee_joseph.version_id.write({
            "date_version": fields.Date.to_date(cls.contract_start_date),
            "contract_date_start": fields.Date.to_date(cls.contract_start_date),
            "contract_date_end": fields.Date.to_date(cls.contract_end_date),
            "name": "contract for Joseph",
            "resource_calendar_id": cls.calendar_40h.id,
            "wage": 5000.0,
        })

    def gantt_resource_employees_working_periods(self, context_dates, resource):
        groups = [{
            "resource_id": [
                resource.id,
                resource.name,
            ],
        }]

        return self.env["planning.slot"]._gantt_resource_employees_working_periods(groups, context_dates["default_start_datetime"], context_dates["default_end_datetime"])

    def test_with_future_contract(self):
        """ Check the working period is only inside the contract created for the resource

            Create a contract in draft but ready in a certain period.
        """
        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_inside_contracts, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertEqual(len(working_periods_for_resource), 1)
        self.assertDictEqual(
            working_periods_for_resource[0],
            {'start': self.contract_start_date, 'end': self.contract_end_date},
            "The working period for that resource should be the contract period only."
        )

        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_outside_contract, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertFalse(working_periods_for_resource, "No working period should be found since the contract period is before the period displayed in the gantt view.")

        self.employee_joseph.version_id.contract_date_end = False
        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_outside_contract, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertDictEqual(
            working_periods_for_resource[0],
            {'start': self.contract_start_date, 'end': False},
            "The working period for that resource should be the whole gantt periods displayed since it is inside the contract period."
        )

    def test_with_running_contract(self):
        """ Check the working period is only inside the contract running of the resource

            Create a running contract
        """
        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_inside_contracts, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertEqual(len(working_periods_for_resource), 1)
        self.assertDictEqual(
            working_periods_for_resource[0],
            {'start': self.contract_start_date, 'end': self.contract_end_date},
            "The working period for that resource should be the contract period only."
        )

        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_outside_contract, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertFalse(working_periods_for_resource, "No working period should be found since the period displayed in the gantt view is after the contract period.")

        self.assertEqual(
            working_periods_for_resource,
            [],
            "The resource working_periods should be empty with a contract in open state outside contract period in context date",
        )

        self.employee_joseph.version_id.contract_date_end = False
        working_periods = self.gantt_resource_employees_working_periods(self.context_dates_outside_contract, self.resource_joseph)
        working_periods_for_resource = working_periods[self.resource_joseph.id]
        self.assertDictEqual(
            working_periods_for_resource[0],
            {'start': self.contract_start_date, 'end': False},
            "The working period for that resource should be the whole gantt periods displayed since it is inside the contract period."
        )

    def test_new_employee_with_no_contract(self):
        """ Test the working period of a new employee with no contract """

        # Create a new employee with no contract
        employee_hope = self.env['hr.employee'].create({'name': 'Hope'})
        self.assertTrue(employee_hope.version_id, "A default version should be created for a new employee.")
        self.assertFalse(employee_hope.version_id.contract_date_start, "The default version should not yet have a contract start date.")

        # The employee should be considered available for the entire Gantt period.
        context_period = self.context_dates_inside_contracts
        gantt_rows_default = self.gantt_resource_employees_working_periods(context_period, employee_hope.resource_id)

        self.assertDictEqual(
            gantt_rows_default[employee_hope.resource_id.id][0],
            {
                'start': context_period['default_start_datetime'],
                'end': context_period['default_end_datetime']
            },
            "A new employee should be considered available for the full default period."
        )

        # After setting a contract start date, the working period should adjust accordingly.
        employee_hope.version_id.write({'contract_date_start': fields.Date.to_date(self.contract_start_date)})
        gantt_rows_with_start = self.gantt_resource_employees_working_periods(context_period, employee_hope.resource_id)

        self.assertEqual(
            gantt_rows_with_start[employee_hope.resource_id.id][0]['start'],
            self.contract_start_date,
            "The working period's start should now match the contract_date_start."
        )
