# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.fields import Domain
from odoo.addons.mail.tools.discuss import Store


class MailActivity(models.Model):
    _inherit = "mail.activity"

    approval_request_id = fields.Many2one("approval.request", compute="_compute_approval_request_id", search="_search_approval_request_id")
    approver_id = fields.Many2one("approval.approver", compute="_compute_approver_id")

    def _search_approval_request_id(self, operator, value):
        if operator in Domain.NEGATIVE_OPERATORS:
            return NotImplemented
        if operator == 'any':
            operator = 'in'
            if isinstance(value, Domain):
                value = self.env['approval.request']._search(value)
        activity_type_approval_id = self.env.ref("approvals.mail_activity_data_approval")
        return [
            [("res_model", "=", "approval.request")],
            [("activity_type_id", "=", activity_type_approval_id)],
            [("res_id", operator, value)]
        ]

    @api.depends("activity_type_id", "res_id", "res_model")
    def _compute_approval_request_id(self):
        activity_type_approval_id = self.env.ref("approvals.mail_activity_data_approval")
        for activity in self:
            if activity["res_model"] == "approval.request" and activity.activity_type_id == activity_type_approval_id:
                activity.approval_request_id = self.env["approval.request"].browse(activity["res_id"])
            else:
                activity.approval_request_id = None

    @api.depends("user_id", "approval_request_id.approver_ids.user_id")
    def _compute_approver_id(self):
        for activity in self:
            activity.approver_id = activity.approval_request_id.approver_ids.filtered(
                lambda approver: activity.user_id == approver.user_id
            )

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [Store.One("approver_id", ["status"])]
