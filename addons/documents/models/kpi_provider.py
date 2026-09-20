# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class KpiProvider(models.AbstractModel):
    _inherit = 'kpi.provider'

    @api.model
    def get_documents_kpi_summary(self):
        inbox_folder = self.env.ref('documents.document_inbox_folder', raise_if_not_found=False)
        if not inbox_folder or not inbox_folder.active:
            return []

        return [{
            'id': 'documents.inbox',
            'name': _('Inbox'),
            'type': 'integer',
            'value': self.env['documents.document'].search_count([
                    ('folder_id', 'child_of', inbox_folder.id),
                    ('type', '!=', 'folder'),
            ]),
        }]

    @api.model
    def get_kpi_summary(self):
        result = super().get_kpi_summary()
        result.extend(self.get_documents_kpi_summary())
        return result
