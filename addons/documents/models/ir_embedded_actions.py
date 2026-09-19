from odoo import api, models


class IrEmbeddedActions(models.Model):
    _inherit = "ir.embedded.actions"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_documents_can_pin()
        return records

    def write(self, vals):
        self._check_documents_can_pin()
        ret = super().write(vals)
        self._check_documents_can_pin()
        return ret

    def _check_documents_can_pin(self):
        """Check that the current user can edit/create the embedded action."""
        to_check = self.filtered(
            lambda a: a.parent_action_id == self.env.ref("documents.document_action", raise_if_not_found=False)
            and a.parent_res_model == "documents.document",
        )
        if to_check:
            folders = self.env["documents.document"].browse(to_check.mapped("parent_res_id"))
            folders.check_access("write")
