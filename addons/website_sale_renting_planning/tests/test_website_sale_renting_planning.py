import json

from datetime import date
from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import HttpCase


class TestWebsiteSaleRentingPlanning(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(freeze_time("2024-06-15 10:00:00"))
        recurrence_day = cls.env['sale.temporal.recurrence'].create([
            {
                'duration': 1,
                'unit': 'day',
            },
        ])
        cls.material_resource = cls.env['resource.resource'].create([
            {'name': 'Material Resource', 'resource_type': 'material'},
        ])
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Employee',
            'contract_date_start': date.today(),
        })
        cls.planning_role = cls.env["planning.role"].create({
            'name': 'Role',
        })
        cls.product_renting_planning = cls.env["product.product"].create({
            "name": "Product Renting Planning",
            "type": "service",
            "list_price": 100.0,
            "rent_ok": True,
            "website_published": True,
            'planning_enabled': True,
            'planning_role_id': cls.planning_role.id,
        })
        cls.env['product.pricing'].create([
            {
                'recurrence_id': recurrence_day.id,
                'price': 100,
                'product_template_id': cls.product_renting_planning.product_tmpl_id.id,
            },
        ])
        cls.planning_role.sync_shift_rental = True
        cls.planning_partner = cls.env['res.partner'].create({
            'name': 'Customer Credee'
        })

    def test_renting_product_availabilities_with_off_resource(self):
        self.planning_role.resource_ids = self.employee.resource_id
        min_date_str = '2024-06-17 10:00:00'
        max_date_str = '2024-06-23 10:00:00'
        min_date = fields.Datetime.to_datetime(min_date_str)
        payload = self.build_rpc_payload({'product_id': self.product_renting_planning.id, 'min_date': min_date_str, 'max_date': max_date_str})
        headers = {
            'Content-Type': 'application/json',
        }
        url = '/rental/product/availabilities'
        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        renting_availabilities = [
            {'start': '2024-06-17 10:00:00', 'end': '2024-06-22 00:00:00', 'quantity_available': 1},
            {'start': '2024-06-22 00:00:00', 'end': '2024-06-22 23:59:59', 'quantity_available': 0},
            {'start': '2024-06-22 23:59:59', 'end': '2024-06-23 00:00:00', 'quantity_available': 1},
            {'start': '2024-06-23 00:00:00', 'end': '2024-06-23 10:00:00', 'quantity_available': 0},
        ]
        self.assertEqual(result['renting_availabilities'], renting_availabilities)

        self.env['resource.calendar.leaves'].create([{
            'name': "Public Holiday (global)",
            'calendar_id': self.employee.resource_calendar_id.id,
            'date_from': min_date,
            'date_to': '2024-06-19 23:59:59',
            'resource_id': self.employee.resource_id.id,
            'time_type': "leave",
        }])

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        renting_availabilities = [
            {'start': '2024-06-17 10:00:00', 'end': '2024-06-19 23:59:59', 'quantity_available': 0},
            {'start': '2024-06-19 23:59:59', 'end': '2024-06-22 00:00:00', 'quantity_available': 1},
            {'start': '2024-06-22 00:00:00', 'end': '2024-06-22 23:59:59', 'quantity_available': 0},
            {'start': '2024-06-22 23:59:59', 'end': '2024-06-23 00:00:00', 'quantity_available': 1},
            {'start': '2024-06-23 00:00:00', 'end': '2024-06-23 10:00:00', 'quantity_available': 0},
        ]
        self.assertEqual(result['renting_availabilities'], renting_availabilities)
        rental_order = self.env['sale.order'].with_context(in_rental_app=True).create({
            'partner_id': self.planning_partner.id,
            'rental_start_date': '2024-06-20 10:00:00',
            'rental_return_date': '2024-06-22 10:00:00',
            'order_line': [
                Command.create({
                    'product_id': self.product_renting_planning.id,
                    'product_uom_qty': 1,
                }),
            ],
        })
        rental_order.action_confirm()

        response = self.url_open(
            url,
            data=json.dumps(payload),
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        renting_availabilities = [
            {'start': '2024-06-17 10:00:00', 'end': '2024-06-19 23:59:59', 'quantity_available': 0},
            {'start': '2024-06-19 23:59:59', 'end': '2024-06-20 10:00:00', 'quantity_available': 1},
            {'start': '2024-06-20 10:00:00', 'end': '2024-06-22 10:00:00', 'quantity_available': 0},
            {'start': '2024-06-22 10:00:00', 'end': '2024-06-22 23:59:59', 'quantity_available': 0},
            {'start': '2024-06-22 23:59:59', 'end': '2024-06-23 00:00:00', 'quantity_available': 1},
            {'start': '2024-06-23 00:00:00', 'end': '2024-06-23 10:00:00', 'quantity_available': 0},
        ]
        self.assertEqual(result['renting_availabilities'], renting_availabilities)
