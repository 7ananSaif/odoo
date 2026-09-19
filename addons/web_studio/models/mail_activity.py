import contextlib

from odoo import models, fields
from odoo.exceptions import UserError
from odoo.fields import Domain


class MailActivity(models.Model):
    _inherit = "mail.activity"

    studio_approval_request_id = fields.Many2one("studio.approval.request", index=True, ondelete='cascade')

    def _action_done(self, feedback=False, attachment_ids=False):
        activities = self
        approval_activities = self.filtered("studio_approval_request_id")
        if approval_activities:
            approval_requests = approval_activities.sudo().studio_approval_request_id
            domains = []
            pairs = set()
            for request in approval_requests:
                pairs.add((request.res_id, request.rule_id))
                domains.append([
                    "&",
                    ("res_id", "=", request.res_id),
                    ("rule_id", "=", request.rule_id.id)
                ])
            domain = Domain.OR(domains)
            extra_requests = self.env["studio.approval.request"].sudo().search(domain)
            extra_activities_to_mark_as_done = extra_requests.mail_activity_id - approval_activities
            extra_activities_to_mark_as_done = self.env['mail.activity'].browse(extra_activities_to_mark_as_done.ids)
            super(MailActivity, extra_activities_to_mark_as_done)._action_done(feedback=feedback, attachment_ids=attachment_ids)
            for (res_id, rule) in pairs:
                with contextlib.suppress(UserError):
                    # the rule has already been rejected/approved or the user does not enough enough rights (or has
                    # already approved exclusive rules) and is trying to "mark ad done" for another user
                    # this should not prevent the user from marking this as done and should not modify any
                    # approval entry
                    # this means that if another user marks this as done and they have "all the rights" necessary
                    # to approve the action, then their approval will be accepted (under their own name)
                    rule.with_context(
                        prevent_approval_request_unlink=True
                    ).set_approval(res_id, True)
            # since 18.3 activities are not unlinked, but archived -> old ondelete cascade
            # behavior of requests should be done manually
            (approval_requests | extra_requests).unlink()
            activities = self.exists()
        return super(MailActivity, activities)._action_done(feedback=feedback, attachment_ids=attachment_ids)
