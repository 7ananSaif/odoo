from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    peppol_reception_mode = fields.Selection(
        related='company_id.peppol_reception_mode',
        readonly=False,
    )
    documents_account_peppol_folder_id = fields.Many2one(
        related='company_id.documents_account_peppol_folder_id',
        readonly=False
    )
    documents_account_peppol_tag_ids = fields.Many2many(
        related='company_id.documents_account_peppol_tag_ids',
        readonly=False
    )
