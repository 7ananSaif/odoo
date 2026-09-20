# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details
from odoo.addons.planning.tests.common import TestCommonPlanning


class TestCommonForecast(TestCommonPlanning):

    @classmethod
    def setUpProjects(cls):
        Project = cls.env['project.project'].with_context(tracking_disable=True)
        Task = cls.env['project.task'].with_context(tracking_disable=True)

        cls.project_opera = Project.create({
            'name': 'Opera',
            'color': 2,
            'privacy_visibility': 'employees',
        })
        cls.task_opera_place_new_chairs = Task.create({
            'name': 'Add the new chairs in room 9',
            'project_id': cls.project_opera.id,
        })
        cls.project_horizon = Project.create({
            'name': 'Horizon',
            'color': 1,
            'privacy_visibility': 'employees',
        })
        cls.task_horizon_dawn = Task.create({
            'name': 'Dawn',
            'project_id': cls.project_horizon.id,
        })

    def get_by_employee(self, employee):
        return self.env['planning.slot'].search([('employee_id', '=', employee.id)])
