from odoo import models
from odoo.fields import Command, Domain


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _timesheet_create_task_prepare_values(self, project):
        """
        Override to add the calendar_event_id to the task created from a sale order line
        with a calendar event (appointment), and populate tasks field.
        Selected staff are added as users, and resources as tags on the task.
        Applies also to Field Service projects.
        """
        res = super()._timesheet_create_task_prepare_values(project)
        if not (self.calendar_event_id and self.calendar_booking_ids):
            return res
        user_ids = tag_ids = False
        if self.calendar_booking_ids.appointment_type_id.schedule_based_on == 'users':
            user_ids = self.calendar_booking_ids.staff_user_id.ids
        # For resource based scheduling, we set the resource names as tags on the task
        else:
            resource_names = self.calendar_event_id.appointment_resource_ids.mapped('name')
            domain = Domain.OR(Domain('name', '=ilike', resource_name) for resource_name in resource_names)
            existing_tags = self.env['project.tags'].search(domain)
            existing_tags_names = {tag.name.lower() for tag in existing_tags}
            new_tags_names = {resource_name for resource_name in resource_names if resource_name.lower() not in existing_tags_names}
            tag_ids = [Command.set(existing_tags.ids)] + [Command.create({'name': name}) for name in new_tags_names]

        # Questions and answers associated to the appointment form will be displayed in the description of the task
        questions = self.calendar_booking_ids.appointment_type_id.question_ids
        answers = self.calendar_booking_ids.appointment_answer_input_ids
        formatted_answers = []
        for question in questions:
            answer_value = '/'
            if (question_answers := answers.filtered(lambda a: a.question_id == question)):
                # if multiple answers, we display them comma-separated
                if question.question_type == 'checkbox':
                    answer_value = ', '.join(question_answers.value_answer_id.mapped('name'))
                else:
                    answer_value = question_answers.value_text_box or question_answers.value_answer_id.name
            formatted_answers.append(f'<dt><h3>{question.name}</h3></dt><dd>{answer_value}</dd><br/>')
        description = f'<dl>{"".join(formatted_answers)}</dl>'

        res.update({
            'partner_id': self.order_id.partner_shipping_id.id,
            'user_ids': user_ids,
            'tag_ids': tag_ids,
            'description': description,
            'calendar_event_id': self.calendar_event_id.id,
            'planned_date_begin': self.calendar_event_id.start,
            'date_deadline': self.calendar_event_id.stop,
            'allocated_hours': self.calendar_event_id.duration,
        })
        return res

    def _timesheet_create_task(self, project):
        task = super()._timesheet_create_task(project)
        if not (self.calendar_event_id and self.calendar_booking_ids):
            return task
        if self.calendar_event_id.attendee_ids:
            partner_ids = self.calendar_event_id.attendee_ids.mapped('partner_id')
            task.message_subscribe(partner_ids.ids)
        return task

    def _action_confirm(self):
        """ Override: as this method is called when successfully paying the SO, or manually in back-end,
            we consider that the linked bookings can be transformed to a calendar event """
        self.order_line.calendar_event_id.action_unarchive()
        self.order_line.calendar_booking_ids._make_event_from_paid_booking()
        return super()._action_confirm()
