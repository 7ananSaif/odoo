from odoo.tests import tagged
from odoo import Command

from .test_approvals import TestStudioApprovalsCommon


@tagged('mail_activity_mixin', "-at_install", "post_install")
class TestApprovalsActivity(TestStudioApprovalsCommon):
    def test_approve_via_activity(self):
        IrModel = self.env["ir.model"]

        self.env["studio.approval.rule"].create([
            {
                "name": "Rule 1",
                "model_id": IrModel._get("test.studio.model_action").id,
                "method": "action_confirm",
                "approval_group_id": self.env.ref("base.group_user").id,
                "approver_ids": [Command.link(self.admin_user.id)],
                "users_to_notify": [Command.link(2)],
                "exclusive_user": True,
            },
            {
                "name": "Rule 2",
                "model_id": IrModel._get("test.studio.model_action").id,
                "method": "action_confirm",
                "approval_group_id": self.env.ref("base.group_user").id,
                "approver_ids": [Command.link(self.admin_user.id)],
                "users_to_notify": [Command.link(2)],
                "exclusive_user": True,
            }
        ])

        model_action = self.env["test.studio.model_action"].create({
            "name": "test"
        })

        with self.with_user("demo"):
            self.env["test.studio.model_action"].browse(model_action.id).action_confirm()

        self.assertFalse(model_action.confirmed)
        self.assertEqual(model_action.activity_ids.summary, "Grant Approval")
        spec = self.env["studio.approval.rule"].get_approval_spec([dict(model="test.studio.model_action", method="action_confirm", action_id=False, res_id=model_action.id)])
        spec = dict(spec["test.studio.model_action"])[model_action.id, "action_confirm", False]
        self.assertEqual(len(spec["entries"]), 1)
        self.assertEqual(len(spec["rules"]), 2)
        self.assertTrue(spec["entries"][0]["approved"])

        model_action.activity_ids.action_feedback()
        spec = self.env["studio.approval.rule"].get_approval_spec([dict(model="test.studio.model_action", method="action_confirm", action_id=False, res_id=model_action.id)])
        spec = dict(spec["test.studio.model_action"])[model_action.id, "action_confirm", False]
        self.assertEqual(len(spec["entries"]), 2)
        self.assertEqual(len(spec["rules"]), 2)
        self.assertTrue(all(e["approved"] for e in spec["entries"]))
        self.assertFalse(model_action.activity_ids)
