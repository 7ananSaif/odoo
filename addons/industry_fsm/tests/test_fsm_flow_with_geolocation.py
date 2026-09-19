# Part of Odoo. See LICENSE file for full copyright and licensing details

from freezegun import freeze_time
from markupsafe import Markup

from odoo.addons.http_routing.tests.common import MockRequest
from odoo.tests import tagged

from .common import TestIndustryFsmCommon


@tagged('post_install', '-at_install')
class TestFsmFlowWithGeolocation(TestIndustryFsmCommon):
    def test_start_timer_with_geolocation(self):
        self.fsm_project.allow_geolocation = True
        task_with_george_user = self.task.with_user(self.george_user)
        geolocation_context = {
            "geolocation": {
                "success": True,
                "latitude": 10,
                "longitude": 13,
            }
        }

        expected_time = '2017-01-01 00:00:00'
        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            with freeze_time(expected_time):
                task_with_george_user.with_context(geolocation_context).action_timer_start()

        self.assertEqual(self.task.message_ids.sorted('create_date')[0].body, Markup('<p>Timer started at: 01/01/2017 12:00:00 AM<br>GPS Coordinates: Namur, Belgium (10, 13) <a href="https://maps.google.com?q=10,13" target="_blank">View on Map</a></p>'))

        expected_time = '2017-01-01 12:20:00'
        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            with freeze_time(expected_time):
                action = task_with_george_user.action_timer_stop()
                geolocation_context["geolocation"]["latitude"] = 200.56
                geolocation_context["geolocation"]["longitude"] = 300.25
                wizard = self.env['hr.timesheet.stop.timer.confirmation.wizard'] \
                    .with_context({**action['context'], **geolocation_context}) \
                    .with_user(self.george_user) \
                    .new({})
                wizard.action_save_timesheet()

        self.assertEqual(self.task.message_ids.sorted('create_date')[0].body, Markup('<p>Timer stopped at: 01/01/2017 12:20:00 PM<br>GPS Coordinates: Namur, Belgium (200.56, 300.25) <a href="https://maps.google.com?q=200.56,300.25" target="_blank">View on Map</a></p>'))

    def test_start_timer_with_geolocation_with_denied_geolocation_permissions(self):
        self.fsm_project.allow_geolocation = True
        task_with_george_user = self.task.with_user(self.george_user)
        geolocation_context = {
            "geolocation": {
                "success": False,
                "message": "Location error: {Error returned by the browser, related to denied permission or maybe something else} e.g User denied Geolocation",
            }
        }

        expected_time = '2017-01-01 00:00:00'
        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            with freeze_time(expected_time):
                task_with_george_user.with_context(geolocation_context).action_timer_start()

        self.assertEqual(self.task.message_ids.sorted('create_date')[0].body, Markup('<p>Timer started at: 01/01/2017 12:00:00 AM<br>Location error: {Error returned by the browser, related to denied permission or maybe something else} e.g User denied Geolocation</p>'))

        expected_time = '2017-01-01 12:20:00'
        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            with freeze_time(expected_time):
                action = task_with_george_user.action_timer_stop()
                geolocation_context["geolocation"]["latitude"] = 200.56
                geolocation_context["geolocation"]["longitude"] = 300.25
                wizard = self.env['hr.timesheet.stop.timer.confirmation.wizard'] \
                    .with_context({**action['context'], **geolocation_context}) \
                    .with_user(self.george_user) \
                    .new({})
                wizard.action_save_timesheet()

        self.assertEqual(self.task.message_ids.sorted('create_date')[0].body, Markup('<p>Timer stopped at: 01/01/2017 12:20:00 PM<br>Location error: {Error returned by the browser, related to denied permission or maybe something else} e.g User denied Geolocation</p>'))
