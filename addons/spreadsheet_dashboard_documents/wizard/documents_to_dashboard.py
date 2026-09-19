# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models


class SpreadsheetDocumentToDashboard(models.TransientModel):
    _name = 'spreadsheet.document.to.dashboard'
    _description = "Create a dashboard from a spreadsheet document"

    name = fields.Char(
        "Dashboard Name",
        required=True,
        compute="_compute_name",
        store=True,
        readonly=False,
        precompute=True,
    )
    document_id = fields.Many2one(
        "documents.document",
        readonly=True,
        required=True,
        domain=[("handler", "=", "spreadsheet")],
    )
    dashboard_group_id = fields.Many2one("spreadsheet.dashboard.group", string="Dashboard Section", required=True)
    group_ids = fields.Many2many(
        "res.groups", default=lambda self: self._default_group_ids(), string="Access Groups"
    )

    def _default_group_ids(self):
        return self.env["spreadsheet.dashboard"].default_get(["group_ids"])["group_ids"]

    @api.depends("document_id.name")
    def _compute_name(self):
        for wizard in self:
            wizard.name = wizard.document_id.name

    def create_dashboard(self):
        self.ensure_one()
        dashboard = self.env["spreadsheet.dashboard"].create(
            {
                "name": self.name,
                "dashboard_group_id": self.dashboard_group_id.id,
                "group_ids": self.group_ids.ids,
                "spreadsheet_data": self.document_id._get_spreadsheet_serialized_snapshot(),
            }
        )
        # transfer the comments to the dashboard
        self.env["spreadsheet.cell.thread"].sudo().search([("document_id", "=", self.document_id.id)])\
            .write({"dashboard_id": dashboard.id, "document_id": False})
        self.document_id._delete_comments_from_data()

        # move the document to the archive
        self.document_id.action_archive()
        return {
            "type": "ir.actions.client",
            "tag": "action_spreadsheet_dashboard",
            "name": self.name,
            "target": "main",
            "params": {
                "dashboard_id": dashboard.id,
            },
        }
