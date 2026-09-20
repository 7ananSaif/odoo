from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import frozendict


class DocumentsAccessTracking(models.Model):
    _name = 'documents.access.tracking'
    _description = 'Document Access Tracking'
    _log_access = False

    changes = fields.Json(string='Changes need to be tracked', required=True)
    documents = fields.Json(string='Impacted Document Ids', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    @api.model
    def _create_access_tracking(self, changes_by_document_dict):
        documents_by_changes = defaultdict(list)
        for document_id, changes in changes_by_document_dict.items():
            documents_by_changes[frozendict(changes)].append(document_id)

        batch_size = int(self.env['ir.config_parameter'].sudo().get_param('documents.tracking_batch_size', '500'))
        for changes, documents in documents_by_changes.items():
            self.sudo().create([
                {
                    'changes': changes,
                    'documents': documents[offset: offset + batch_size],
                    'user_id': self.env.user.id,
                } for offset in range(0, len(documents), batch_size)
            ])

        self.env.ref('documents.ir_cron_documents_access_tracking')._trigger()

    @api.model
    def _cron_generate_tracking(self):
        tracking_id = self.search([], limit=1)
        if not tracking_id:
            self.env['ir.cron']._commit_progress(remaining=0)
            return

        tracking_id._create_message_track()
        tracking_id.unlink()
        self.env['ir.cron']._commit_progress(processed=len(tracking_id), remaining=self.search_count([]))

    def _create_message_track(self):
        self.ensure_one()
        document_ids = self.env['documents.document'].browse(self.documents)
        if initial_values := self._get_initial_values():
            if 'members' in self.changes:
                self._add_pre_commit_members_data()
            document_ids.with_user(self.user_id)._message_track([
                'access_internal',
                'access_via_link',
                'is_access_via_link_hidden',
            ], initial_values)
        else:
            body = self._get_members_change_template_body()
            document_ids.with_user(self.user_id)._message_log_batch(
                bodies={doc_id: body for doc_id in document_ids.ids}
            )

    def _get_initial_values(self):
        self.ensure_one()
        fields_list = ['access_internal', 'access_via_link', 'is_access_via_link_hidden']
        common_values = {
            field: self.changes[field] for field in fields_list if field in self.changes
        }
        return {doc_id: common_values for doc_id in self.documents if common_values}

    def _add_pre_commit_members_data(self):
        self.ensure_one()
        common_body = self._get_members_change_template_body()
        self.env.cr.precommit.data.setdefault('mail.tracking.message.documents.document', {
            doc_id: common_body for doc_id in self.documents
        })

    def _get_members_change_template_body(self):
        self.ensure_one()
        return self.env['ir.qweb']._render('documents.tracking_access_members_change', {
            'created_access': self.changes['members']['added'],
            'updated_access': self.changes['members']['updated'],
            'removed_access': self.changes['members']['removed'],
            'partner_map': self._get_partners_mapping(),
        }, lang=self.user_id.lang, minimal_qcontext=True)

    def _get_partners_mapping(self):
        self.ensure_one()
        partner_map = {}
        members_dict = self.changes['members']
        for operation in ['added', 'updated']:
            # must cast into int because fields.Json set all keys in string
            partner_ids = self.env['res.partner'].browse([int(id) for id in members_dict[operation]])
            partner_map.update(dict(zip(members_dict[operation].keys(), partner_ids)))

        partner_ids = self.env['res.partner'].browse(members_dict['removed'])
        partner_map.update(dict(zip(members_dict['removed'], partner_ids)))

        return partner_map
