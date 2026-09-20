# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from unittest.mock import patch
from dateutil.relativedelta import relativedelta

import json
import requests

from odoo.addons.l10n_be_hr_payroll_dimona.models.hr_version import HrVersion
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n', 'dimona')
@patch.object(HrVersion, '_dimona_authenticate', lambda version, company, declare=True: 'dummy-token')
@patch.object(HrVersion, '_cron_l10n_be_check_dimona', lambda version: True)
class TestDimona(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.belgium = cls.env.ref('base.be')

        cls.env.company.write({
            'country_id': cls.belgium.id,
            'onss_registration_number': '12548245',
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'niss': '93051822361',
            'private_street': '23 Test Street',
            'private_city': 'Test City',
            'private_zip': '6800',
            'private_country_id': cls.belgium.id,
            'wage': 2000,
            'date_version': date.today() + relativedelta(day=1, months=1),
            'contract_date_start': date.today() + relativedelta(day=1, months=1),
            'sex': 'male',
        })

        cls.version = cls.employee.version_id

    def test_dimona_open_classic(self):
        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/2029409422'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)

    def test_dimona_open_foreigner(self):
        self.employee.write({
            'birthday': date(1991, 7, 28),
            'place_of_birth': 'Paris',
            'country_of_birth': self.env.ref('base.fr').id,
            'country_id': self.env.ref('base.fr').id,
            'sex': 'male',
        })

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
            'without_niss': True,
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/2029409422'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)

    def test_dimona_open_student(self):
        self.version.write({
            'structure_type_id': self.env.ref('l10n_be_hr_payroll.structure_type_student').id,
            'l10n_be_dimona_planned_hours': 130,
            'date_end': date.today() + relativedelta(months=1, day=31),
        })
        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'in',
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/2029409422'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)

    def test_dimona_close(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })
        self.version.contract_date_end = date.today() + relativedelta(months=1, day=31)

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'out',
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/309320239'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_update(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })
        self.version.contract_date_end = date.today() + relativedelta(months=1, day=31)

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'update',
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/309320239'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_cancel(self):
        self.version.l10n_be_dimona_declaration_id = self.env['l10n.be.dimona.declaration'].create({
                'name': '2029409422',
                'version_id': self.version.id,
                'employee_id': self.version.employee_id.id,
                'company_id': self.version.company_id.id,
            })

        wizard = self.env['l10n.be.dimona.wizard'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'declaration_type': 'cancel',
        })

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/309320239'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            wizard.submit_declaration()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '309320239')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

    def test_dimona_flow_classic(self):
        # pylint: disable=function-redefined
        self.version.date_version = date(2025, 9, 26)
        self.version.contract_date_start = date(2025, 9, 26)

        # No dimona yet
        self.assertFalse(self.employee.l10n_be_dimona_declaration_id)
        self.assertFalse(self.employee.l10n_be_last_dimona_declaration_id)

        # Needs Dimona IN is true
        self.assertTrue(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/2029409422'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_open_dimona()

        # Dimona IN created
        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '2029409422')
        self.assertFalse(self.version.l10n_be_dimona_declaration_id.state)

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Content-Type': 'application/json'}
            response._content = json.dumps({
                "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/2029409422", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "dimonaIn": {"features": {"workerType": "OTH", "jointCommissionNumber": "XXX"}, "startDate": "2025-09-26"}, "employer": {"employerId": 12548245, "enterpriseNumber": "477472701"}, "declarationStatus": {"period": {"id": 2029409422, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/2029409422"}, "result": "A", "declarationId": 2029409422}
            }).encode()
            response.status_code = 200
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        # Now, update contract start date
        self.version.date_version = date(2025, 7, 3)
        self.version.contract_date_start = date(2025, 7, 3)

        # Dimona update button is displayed
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertTrue(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/656309296521'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_update_dimona()

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309296521')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Content-Type': 'application/json'}
            response._content = json.dumps({
                "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/656309296521", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 12548245, "enterpriseNumber": "477472701"}, "dimonaUpdate": {"periodId": 656309292174, "startDate": "2025-07-03"}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309296521}
                }).encode()
            response.status_code = 200
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')

        # Now, set contract end date
        self.version.contract_date_end = date(2025, 9, 24)

        # Dimona out button is displayed
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertTrue(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/656309314911'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_close_dimona()

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309314911')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Content-Type': 'application/json'}
            response._content = json.dumps({
                "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/declarations/656309314911", "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 12548245, "enterpriseNumber": "477472701"}, "dimonaOut": {"endDate": "2025-09-24", "periodId": 656309292174}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309314911}
            }).encode()
            response.status_code = 200
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')

        # Last, archive employee because contract was cancelled
        self.employee.active = False

        # Dimona out button is displayed
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertTrue(self.employee.l10n_be_needs_dimona_cancel)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Location': 'foo/bar/blork/656309322385'}
            response.status_code = 201
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_cancel_dimona()

        # No displayed button, nothing to do
        self.assertFalse(self.employee.l10n_be_needs_dimona_in)
        self.assertFalse(self.employee.l10n_be_needs_dimona_update)
        self.assertFalse(self.employee.l10n_be_needs_dimona_out)
        self.assertFalse(self.employee.l10n_be_needs_dimona_cancel)

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.name, '2029409422')
        self.assertEqual(self.version.l10n_be_last_dimona_declaration_id.name, '656309322385')
        self.assertFalse(self.version.l10n_be_last_dimona_declaration_id.state)

        def _patched_request(*args, **kwargs):
            response = requests.Response()
            response.headers = {'Content-Type': 'application/json'}
            response._content = json.dumps({
                "worker": {"ssin": "93051822361", "gender": "1", "birthDate": "1991-11-11", "givenName": "TEST", "familyName": "EMPLOYEE", "givenNames": "TEST EMPLOYEE", "nationality": 150}, "employer": {"employerId": 12548245, "enterpriseNumber": "477472701"}, "dimonaCancel": {"periodId": 656309292174}, "declarationStatus": {"period": {"id": 656309292174, "href": "https://services-sim.socialsecurity.be/REST/dimona/v2/periods/656309292174"}, "result": "A", "declarationId": 656309322385}
            }).encode()
            response.status_code = 200
            return response

        with patch('requests.sessions.Session.request', side_effect=_patched_request):
            self.employee.action_check_dimona()

        self.assertEqual(self.version.l10n_be_dimona_declaration_id.state, 'A')
