from odoo import models


class L10n_Be_ReportsPeriodicVatXmlExport(models.TransientModel):
    _name = 'l10n_be_reports.vat.return.submission.wizard'
    _inherit = 'account.return.submission.wizard'
    _description = "Belgian Periodic VAT Report Export Wizard"

    def print_xml(self):
        xml_file = self.return_id.attachment_ids.filtered(lambda a: a.name.endswith(".xml"))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{xml_file.id}?download=true",
            "target": "download",
        }
