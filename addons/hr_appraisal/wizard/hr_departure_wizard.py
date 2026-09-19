# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    delete_appraisal = fields.Boolean(string="Delete Future Appraisals", default=True,
        help="Delete all appraisal after contract end date.")

    def action_register_departure(self):
        action = super().action_register_departure()
        if self.delete_appraisal:
            future_appraisals = self.env["hr.appraisal"].search([
                ('employee_id', 'in', self.employee_ids.ids),
                ('state', 'in', ['1_new', '2_pending'])])
            future_appraisals.unlink()
        return action
