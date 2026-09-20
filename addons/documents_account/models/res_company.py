# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = "res.company"

    account_folder_id = fields.Many2one(
        'documents.document', string="Accounting Folder", check_company=True,
        compute='_compute_account_folder_id', precompute=True, store=True, readonly=False,
        domain=[('type', '=', 'folder'), ('shortcut_document_id', '=', False)])

    def _compute_account_folder_id(self):
        self.filtered(lambda c: not c.account_folder_id).account_folder_id = (
            self.env.ref('documents.document_finance_folder', raise_if_not_found=False))

    def _get_used_folder_ids_domain(self, folder_ids):
        return super()._get_used_folder_ids_domain(folder_ids) | Domain('account_folder_id', 'in', folder_ids)
