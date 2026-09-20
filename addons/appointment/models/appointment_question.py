# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AppointmentQuestion(models.Model):
    _name = 'appointment.question'
    _description = "Appointment Questions"
    _order = "sequence,id"

    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence')
    appointment_type_ids = fields.Many2many('appointment.type', relation='appointment_type_appointment_question_rel', string='Appointment Types')
    appointment_count = fields.Integer('# Appointments', compute='_compute_appointment_count')
    is_default = fields.Boolean('Default question', help="Include by default in new appointment types.")
    is_reusable = fields.Boolean('Is Reusable',
        compute='_compute_is_reusable', default=True, store=True, readonly=False,
        help="Will appear in the list of available questions when adding one in any appointment. Always true for default questions.")
    name = fields.Char('Question', translate=True, required=True)
    placeholder = fields.Char('Placeholder', translate=True)
    question_required = fields.Boolean('Mandatory Answer')
    question_type = fields.Selection([
        ('char', 'Single line text'),
        ('text', 'Multi-line text'),
        ('phone', 'Phone Number'),
        ('select', 'Dropdown (one answer)'),
        ('radio', 'Radio (one answer)'),
        ('checkbox', 'Checkboxes (multiple answers)')], 'Answer Type', default='char', required=True)
    answer_ids = fields.One2many('appointment.answer', 'question_id', string='Available Answers', copy=True)
    answer_input_ids = fields.One2many('appointment.answer.input', 'question_id', string='Submitted Answers')
    extra_comment = fields.Html('Extra Comment', translate=True,
        help="This will appear below the question in the appointment form.")

    _check_default_question_is_reusable = models.Constraint(
        'CHECK(is_default IS DISTINCT FROM TRUE OR is_reusable IS TRUE)',
        "A default question must be reusable."
    )

    @api.constrains('question_type', 'answer_ids')
    def _check_question_type(self):
        incomplete_questions = self.filtered(lambda question: question.question_type in ['select', 'radio', 'checkbox'] and not question.answer_ids)
        if incomplete_questions:
            raise ValidationError(
                _('The following question(s) do not have any selectable answers : %s',
                  ', '.join(incomplete_questions.mapped('name'))
                  )
            )

    @api.depends('appointment_type_ids')
    def _compute_appointment_count(self):
        appointment_data = self.env["appointment.type"]._read_group(
            [('question_ids', 'in', self.ids)],
            ['question_ids'],
            ['__count']
        )
        mapped_data = {appointment_question.id: count for appointment_question, count in appointment_data}
        for question in self:
            if not question.id:  # new record
                question.appointment_count = len(question.appointment_type_ids)
            else:
                question.appointment_count = mapped_data.get(question.id, 0)

    @api.depends('is_default')
    def _compute_is_reusable(self):
        for question in self:
            if question.is_default:
                question.is_reusable = True

    def action_view_question_answer_inputs(self):
        """ Allow analyzing the answers to a question on an appointment in a convenient way:
        - A graph view showing counts of each suggested answers for multiple-choice questions:
        select / radio / checkbox. (Along with secondary pivot and list views)
        - A list view showing textual answers values for char / text questions"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("appointment.appointment_answer_input_action")
        if self.question_type in ['select', 'radio', 'checkbox']:
            action['views'] = [(False, 'pivot'), (False, 'graph'), (False, 'list'), (False, 'form')]
        elif self.question_type in ['char', 'text', 'phone']:
            action['views'] = [(False, 'list'), (False, 'form')]
        action['context'] = {
            'create': False,
            'search_default_question_id': self.id,
        }
        if appointment_id := self.env.context.get('search_default_appointment_type_id'):
            action['context'].update(search_default_appointment_type_id=appointment_id)
        return action

    def action_view_appointment_types(self):
        action = self.env["ir.actions.actions"]._for_xml_id("appointment.appointment_type_action")
        action['domain'] = [('question_ids', 'in', self.ids)]
        return action
