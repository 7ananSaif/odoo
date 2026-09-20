# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time, timedelta
from odoo import models


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    def action_register_departure(self):
        action = super().action_register_departure()

        departure_date = datetime.combine(self.departure_date + timedelta(days=1), time.min)
        planning_slots = self.env['planning.slot'].sudo().search([
            ('employee_id', 'in', self.employee_ids.ids),
            ('end_datetime', '>=', departure_date),
        ])
        planning_slots._manage_archived_resources(departure_date)
        return action
