# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests
from odoo.addons.pos_restaurant.tests.test_frontend import TestFrontend
from odoo import fields
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time



@odoo.tests.tagged('post_install', '-at_install')
class TestUi(TestFrontend):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids += cls.quick_ref('appointment.group_appointment_manager')

        cls.appointment_type = cls.env['appointment.type'].create({
            'appointment_tz': 'US/Eastern',
            'event_videocall_source': False,
            'is_auto_assign': True,
            'name': 'Table Booking Test',
            'manage_capacity': True,
            'manual_confirmation_percentage': 0.8,
            'schedule_based_on': 'resources',
        })

        cls.pos_config.write({
            'module_pos_appointment': True,
            'appointment_type_id': cls.appointment_type.id,
        })

        cls.main_floor_table_4 = cls.env['restaurant.table'].search([
            ('table_number', '=', 4),
            ('floor_id', '=', cls.main_floor.id)
        ], limit=1)

        cls.table_4_resource = cls.env['appointment.resource'].create({
            'name': 'Test Main Floor - Table 4',
            'capacity': 2,
            'appointment_type_ids': [(6, 0, [cls.appointment_type.id])],
            'pos_table_ids': [(6, 0, [cls.main_floor_table_4.id])]
        })

        cls.table_5_resource = cls.env['appointment.resource'].create({
            'name': 'Test Main Floor - Table 5',
            'capacity': 2,
            'appointment_type_ids': [(6, 0, [cls.appointment_type.id])],
            'pos_table_ids': [(6, 0, [cls.main_floor_table_5.id])]
        })

    def test_pos_restaurant_appointment_tour_basic(self):
        now = fields.Datetime.now()
        self.env['calendar.event'].create([{
                    'name': "Test Lunch",
                    'start': now + relativedelta(minutes=30),
                    'stop': now + relativedelta(minutes=150),
                    'appointment_type_id': self.appointment_type.id,
                    'booking_line_ids': [(0, 0, {'appointment_resource_id': self.table_5_resource.id, 'capacity_reserved': 2})],
                }, {
                    'name': "Tomorrow Appointment",
                    'start': now + relativedelta(days=1, minutes=30),
                    'stop': now + relativedelta(days=1, minutes=90),
                    'appointment_type_id': self.appointment_type.id,
                    'booking_line_ids': [(0, 0, {'appointment_resource_id': self.table_4_resource.id, 'capacity_reserved': 2})],
                }])
        # open a session, the /pos/ui controller will redirect to it
        self.pos_config.with_user(self.pos_admin).open_ui()

        self.start_pos_tour('RestaurantAppointmentTour', login="pos_admin")

    @freeze_time('2025-08-27 12:18:56')
    def test_appointment_kanban_view(self):
        self.start_pos_tour("test_appointment_kanban_view", login="pos_admin")
        self.start_pos_tour('DuplicateFloorCalendarResource', login="pos_admin")

        floor = self.env['restaurant.floor'].search([('name', '=', 'Main Floor (copy)'), ('pos_config_ids', 'in', self.pos_config.id)], limit=1)
        for table in floor.table_ids:
            self.assertIn(
                self.appointment_type.id,
                table.appointment_resource_id.appointment_type_ids.ids,
                f"Table {table.table_number} resource does not include expected appointment type."
            )
