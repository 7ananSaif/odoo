
from odoo import Command
from odoo.addons.project.tests.test_project_base import TestProjectCommon
from odoo.addons.appointment.tests.common import AppointmentCommon
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import users, tagged

from datetime import datetime
from freezegun import freeze_time
import re

@tagged('post_install', '-at_install')
class TestProjectAppointmentTask(TestProjectCommon, AppointmentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.project = cls.env['project.project'].create({
            'name': 'Project Test APT',
            'company_id': cls.env.company.id,
        })

        # create additional users to invite as guests in the appointment
        cls.test_user_1 = mail_new_test_user(
            cls.env, login='test1',
            name='Test User 1', email='test1@example.com',
            groups='base.group_user',
        )
        cls.test_user_2 = mail_new_test_user(
            cls.env, login='test2',
            name='Test User 2', email='test2@example.com',
            groups='base.group_user',
        )

        # create a product associated with project defined in common
        cls.product = cls.env['product.product'].create({
            'name': 'Project Test APT Product',
            'company_id': cls.env.company.id,
            'project_id': cls.project.id,
            'type': 'service',
            'list_price': 100,
            "service_policy": "ordered_prepaid",
            "service_tracking": "task_global_project",
            "service_type": "manual",
        })

        # define 2 types of appointment (one for users and one for resources)
        paid_apt_common_values = {
            'appointment_tz': 'UTC',
            'has_payment_step': True,
            'min_schedule_hours': 1.0,
            'max_schedule_days': 2,
            'product_id': cls.product.id,
            'slot_ids': [Command.create({
                'weekday': str(cls.reference_monday.isoweekday()),
                'start_hour': 14,
                'end_hour': 17,
            })],
            'allow_guests': True,
        }

        cls.appointment_users, cls.appointment_resources = cls.env['appointment.type'].create([{
            'name': 'Test Paid Appointment Type - Users',
            'schedule_based_on': 'users',
            'staff_user_ids': [(4, cls.staff_user_bxls.id)],
            **paid_apt_common_values,
        }, {
            'name': 'Test Paid Appointment Type - Resource',
            'manage_capacity': True,
            'schedule_based_on': 'resources',
            **paid_apt_common_values,
        }])

        cls.resource_1, cls.resource_2 = cls.env['appointment.resource'].create([{
            'appointment_type_ids': cls.appointment_resources.ids,
            'capacity': 3,
            'name': 'APT Resource 1',
        }, {
            'appointment_type_ids': cls.appointment_resources.ids,
            'capacity': 2,
            'name': 'APT Resource 2',
            'shareable': True,
        }])

        cls.start_slot = cls.reference_monday.replace(hour=14)
        cls.stop_slot = cls.reference_monday.replace(hour=15)

        # Define questions and answers for the appointment form (only user type appointment)
        # Types of questions: char, select, radio, checkbox
        cls.appointment_question_single_line_text, cls.appointment_question_dropdown, cls.appointment_question_radio, cls.appointment_question_checkbox = cls.env['appointment.question'].create([
            {
                'appointment_type_ids': cls.appointment_users.ids,
                'name': 'How are you ?',
                'question_type': 'char',
            },
            {
                'appointment_type_ids': cls.appointment_users.ids,
                'name': 'How do you feel?',
                'question_type': 'select',
                'answer_ids': [
                    Command.create({'name': name}) for name in ['Happy', 'Sad', 'Neutral']
                ]
            },
            {
                'appointment_type_ids': cls.appointment_users.ids,
                'name': "Don't answer this",
                'question_type': 'radio',
                'answer_ids': [
                    Command.create({'name': name}) for name in ['Ok', 'Not Ok', 'Maybe Ok']
                ]
            },
            {
                'appointment_type_ids': cls.appointment_users.ids,
                'name': 'Select multiple',
                'question_type': 'checkbox',
                'answer_ids': [
                    Command.create({'name': name}) for name in ['odoo', 'oqoo', 'opoo', 'oboo']
                ]
            }
        ])

    @freeze_time('2022-02-13 20:00:00')
    @users('apt_manager')
    def test_project_user_appointment_type_task_population_on_confirmed_so(self):
        """
        Verify that when the SO of a appointment booking of USER type is confirmed,
        a task is created with its data populated, and a reference to the appointment (calendar_event) is created.
        The selected users (named here as staff) should be added as users on the task.
        The questions and answers of the appointment form should be displayed in the description of the task.
        """
        appointment_type = self.appointment_users

        appointment_answer_single_line_text_input_values = {
            'appointment_type_id': appointment_type.id,
            'question_id': self.appointment_question_single_line_text.id,
            'value_text_box': 'I am Good',
        }
        appointment_answer_dropdown_input_values = {
            'appointment_type_id': appointment_type.id,
            'question_id': self.appointment_question_dropdown.id,
            'value_answer_id': self.appointment_question_dropdown.answer_ids.filtered(lambda a: a.name == 'Happy').id,
        }
        appointment_answer_checkbox_input_values = [
            {
                'appointment_type_id': appointment_type.id,
                'question_id': self.appointment_question_checkbox.id,
                'value_answer_id': answer.id
            } for answer in self.appointment_question_checkbox.answer_ids
            if answer.name != 'odoo'
        ]

        # dictionary with the values of the answers for the questions of the appointment form (question_id: answer_value)
        user_answers = {
            self.appointment_question_single_line_text.id: 'I am Good',
            self.appointment_question_dropdown.id: 'Happy',
            self.appointment_question_radio.id: '',
            self.appointment_question_checkbox.id: ['oqoo', 'opoo', 'oboo'],
        }

        booking_values = {
            'appointment_type_id': appointment_type.id,
            'appointment_answer_input_ids': [
                Command.create(appointment_answer_single_line_text_input_values),
                Command.create(appointment_answer_dropdown_input_values),
            ] + [Command.create(values) for values in appointment_answer_checkbox_input_values],
            'booking_line_ids': [Command.create({'appointment_user_id': self.staff_user_bxls.id, 'capacity_reserved': 1, 'capacity_used': 1})],
            'partner_id': self.apt_manager.partner_id.id,   
            'product_id': self.product.id,
            'staff_user_id': self.staff_user_bxls.id,
            'start': self.start_slot,
            'stop': self.stop_slot,
            'guest_ids': [self.test_user_1.partner_id.id, self.test_user_2.partner_id.id],
        }
        calendar_booking = self.env['calendar.booking'].create(booking_values)

        # Create SO (quotation) and SOL linked to booking
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': calendar_booking.partner_id.id,
            'company_id': self.env.company.id,
        })
        self.assertFalse(calendar_booking._filter_unavailable_bookings(), "No unavailable booking should be found")

        cart_values = sale_order._cart_add(
            product_id=appointment_type.product_id.id,
            quantity=1,
            calendar_booking_id=calendar_booking.id,
        )
        self.assertEqual(cart_values['quantity'], 1, "Cart should successfully add 1 product (the appointment)")

        sale_order_line = sale_order.order_line.filtered(lambda line: line.id == cart_values['line_id'])
        self.assertTrue(sale_order_line, "Sale order line should be created after adding the product to the cart")
        self.assertEqual(sale_order_line.calendar_booking_ids, calendar_booking, "Sale order line should be linked to the calendar booking")
        self.assertFalse(sale_order_line.calendar_event_id)

        sale_order.action_confirm()
        task = sale_order_line.task_id
        event = task.calendar_event_id
        self.assertTrue(task, "Task should be created after confirming the sale order")
        self.assertTrue(event, "Calendar event should be created after confirming the sale order")
        self.assertEqual(event, calendar_booking.calendar_event_id, "Calendar event of the task should be linked to the calendar booking")
        self.assertEqual(task.user_ids.ids, calendar_booking.staff_user_id.ids, "Staff users of the booking should be added as users on the task")
        self.assertEqual(task.allocated_hours, event.duration, "Allocated hours of the task should be equal to the duration of the event")
        self.assertEqual(task.planned_date_begin, event.start, "Planned date begin of the task should be equal to the start of the event")
        self.assertEqual(task.date_deadline, event.stop, "Date deadline of the task should be equal to the stop of the event")

        # Assert that the invited guests are followers of the task (remove the staff user and apt manager)
        followers_ids = set(task.message_partner_ids.ids)
        followers_ids.difference_update({self.staff_user_bxls.partner_id.id, self.apt_manager.partner_id.id})
        self.assertEqual(followers_ids, set(calendar_booking.guest_ids.ids), "Invited guests should be followers of the task")

        # Assert the desctiption of the task, which should contain the questions of the appointment form.
        questions = calendar_booking.appointment_type_id.question_ids

        # Define the regular expression pattern (<dt> for questions, <dd> tags for answers)
        reg_pattern = r'<dt><h3>(.*?)<\/h3><\/dt>[\s\S]*?<dd>(.*?)<\/dd>'
        # Find all matches in the description of the task (type is MarkUp so cast it to str)
        matches = re.findall(reg_pattern, str(task.description))

        # Assert that the pair of question and answer are identical in the description of the task
        for match in matches:
            task_question_name, task_answer_value = match
            question = questions.filtered(lambda q: q.name == task_question_name)
            self.assertTrue(question, f"Question {task_question_name} not found in description of task")

            # compare the answers found in the description with the answers prepared for the test `user_answers`
            answer_value = user_answers.get(question.id)
            if not answer_value:
                self.assertEqual(task_answer_value, "/", "When no answer was provided by user, the value should be '/'")
            elif question.question_type == 'checkbox':
                self.assertEqual(set(task_answer_value.split(', ')), set(answer_value), "For multiple answers, the values should be comma-separated")
            else:
                self.assertEqual(task_answer_value, answer_value, "The answer value should be equal to the value provided by the user")

    @freeze_time('2022-02-13 20:00:00')
    def test_project_resource_appointment_type_task_population_on_confirmed_so(self):
        """
        Verify that when the SO of a appointment booking of RESOURCE type is confirmed,
        a task is created with its data populated, and a reference to the appointment (calendar_event) is created.
        The selected resources should be added as tags on the task.
        """
        appointment_type = self.appointment_resources

        booking_values = {
            'appointment_type_id': appointment_type.id,
            'partner_id': self.partner_1.id,
            'product_id': self.product.id,
            'name': 'Project Appointment Booking Resource test',
            'booking_line_ids': [
                Command.create({'appointment_resource_id': self.resource_1.id, 'capacity_reserved': 1, 'capacity_used': 2}),
                Command.create({'appointment_resource_id': self.resource_2.id, 'capacity_reserved': 1}),
            ],
            'start': self.start_slot,
            'stop': self.stop_slot,
        }
        calendar_booking = self.env['calendar.booking'].create(booking_values)

        # Create SO (quotation) and SOL linked to booking
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner_1.id,
            'company_id': self.env.company.id,
        })
        self.assertFalse(calendar_booking._filter_unavailable_bookings(), "No unavailable booking should be found")

        cart_values = sale_order._cart_add(
            product_id=appointment_type.product_id.id,
            quantity=1,
            calendar_booking_id=calendar_booking.id,
        )
        self.assertEqual(cart_values['quantity'], 1, "Cart should successfully add 1 product (the appointment)")

        sale_order_line = sale_order.order_line.filtered(lambda line: line.id == cart_values['line_id'])
        self.assertTrue(sale_order_line, "Sale order line should be created after adding the product to the cart")
        self.assertEqual(sale_order_line.calendar_booking_ids, calendar_booking, "Sale order line should be linked to the calendar booking")
        self.assertFalse(sale_order_line.calendar_event_id)

        sale_order.action_confirm()
        task = sale_order_line.task_id
        event = task.calendar_event_id
        self.assertTrue(task, "Task should be created after confirming the sale order")
        self.assertTrue(event, "Calendar event should be created after confirming the sale order")
        self.assertEqual(event, calendar_booking.calendar_event_id, "Calendar event of the task should be linked to the calendar booking")
        self.assertEqual(set(task.tag_ids.mapped('name')), set(calendar_booking.booking_line_ids.appointment_resource_id.mapped('name')),
                         "Selected resources should be added as tags on the task")
        self.assertEqual(task.allocated_hours, event.duration, "Allocated hours of the task should be equal to the duration of the event")
        self.assertEqual(task.planned_date_begin, event.start, "Planned date begin of the task should be equal to the start of the event")
        self.assertEqual(task.date_deadline, event.stop, "Date deadline of the task should be equal to the stop of the event")
