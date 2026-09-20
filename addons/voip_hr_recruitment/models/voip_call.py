from odoo import fields, models


class VoipCall(models.Model):
    _inherit = "voip.call"

    application_count = fields.Integer(related="partner_id.applicant_ids.application_count")

    def voip_action_view_applications(self):
        return self.env["hr.applicant"].action_open_applications()
