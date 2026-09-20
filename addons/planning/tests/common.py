# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MO

from odoo.tests.common import TransactionCase, HttpCase

from odoo.addons.mail.tests.common import mail_new_test_user


class TestCommonPlanning(TransactionCase):
    def get_by_employee(self, employee):
        return self.env['planning.slot'].search([('employee_id', '=', employee.id)])

    @classmethod
    def setUpEmployees(cls):
        cls.env.user.tz = "Europe/Brussels"
        cls.employee_joseph = cls.env['hr.employee'].create({
            'name': 'joseph',
            'work_email': 'joseph@a.be',
            'tz': 'UTC',
            'employee_type': 'freelance',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_joseph = cls.employee_joseph.resource_id
        cls.employee_bert = cls.env['hr.employee'].create({
            'name': 'bert',
            'work_email': 'bert@a.be',
            'tz': 'UTC',
            'employee_type': 'freelance',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_bert = cls.employee_bert.resource_id
        cls.employee_janice = cls.env['hr.employee'].create({
            'name': 'janice',
            'work_email': 'janice@a.be',
            'tz': 'America/New_York',
            'employee_type': 'freelance',
            'create_date': '2015-01-01 00:00:00',
        })
        cls.resource_janice = cls.employee_janice.resource_id
        cls.planning_manager_user = mail_new_test_user(
            cls.env, login='planning_manager_user', groups='planning.group_planning_manager', name='Planning Manager User'
        )

    @classmethod
    def setUpDates(cls):
        cls.random_date = datetime(2020, 11, 27)  # it doesn't really matter but it lands on a Friday
        cls.random_sunday_date = datetime(2024, 3, 10)  # this should be a Sunday and thus a closing day
        cls.random_monday_date = datetime(2024, 3, 11)  # this should be a Monday

    @classmethod
    def setUpCalendars(cls):
        cls.flex_40h_calendar, cls.flex_50h_calendar, cls.company_calendar = cls.env['resource.calendar'].create([
            {
                'name': 'Flexible 40h/week',
                'tz': 'UTC',
                'hours_per_day': 8.0,
                'flexible_hours': True,
            }, {
                'name': 'Flexible 50h/week',
                'tz': 'UTC',
                'hours_per_day': 10.0,
                'flexible_hours': True,
            }, {
                'name': 'Classic 40h/week',
                'tz': 'UTC',
                'hours_per_day': 8.0,
                'attendance_ids': [
                    (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                    (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                    (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                    (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 6, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 15, 'day_period': 'afternoon'}),
                    (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                    (0, 0, {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                    (0, 0, {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'})
                ],
            },
        ])


class TestUiCommon(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.flex_40h_calendar = cls.env['resource.calendar'].create({
            'name': 'Flexible 40h/week',
            'tz': 'UTC',
            'hours_per_day': 8.0,
            'flexible_hours': True,
            'full_time_required_hours': 40,
        })
        cls.employee_thibault = cls.env['hr.employee'].create({
            'name': 'Aaron',
            'work_email': 'aaron@a.be',
            'tz': 'Europe/Brussels',
            'employee_type': 'freelance',
            'resource_calendar_id': cls.flex_40h_calendar.id,
        })
        start = datetime.now() + relativedelta(weekday=MO(-1), hour=10, minute=0, second=0, microsecond=0)
        cls.env['planning.slot'].create({
            'start_datetime': start,
            'end_datetime': start + relativedelta(hour=11),
        })


class TestPlanningContractCommon(TestCommonPlanning):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setUpEmployees()
        cls.setUpDates()
        cls.employee_bert['employee_type'] = 'employee'
        cls.calendar_35h = cls.env['resource.calendar'].create({
            'name': '35h calendar',
            'attendance_ids': [
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Lunch', 'dayofweek': '0', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Monday Evening', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Lunch', 'dayofweek': '1', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Tuesday Evening', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Lunch', 'dayofweek': '2', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Wednesday Evening', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Lunch', 'dayofweek': '3', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Thursday Evening', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Lunch', 'dayofweek': '4', 'hour_from': 12, 'hour_to': 13, 'day_period': 'lunch'}),
                (0, 0, {'name': 'Friday Evening', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 16, 'day_period': 'afternoon'})
            ]
        })
        cls.calendar_40h = cls.env['resource.calendar'].create({'name': 'Default calendar'})
        cls.calendar_30h_flex = cls.env['resource.calendar'].create({
            'name': '30h flex calendar',
            'flexible_hours': True,
            'attendance_ids': [],
            'hours_per_day': 6,
        })
