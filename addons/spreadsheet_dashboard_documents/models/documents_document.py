from odoo import models


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    def _get_spreadsheet_metadata(self, access_token=None):
        data = super()._get_spreadsheet_metadata(access_token)
        return dict(data, can_add_to_dashboard=self.env['spreadsheet.dashboard'].has_access('create'))
