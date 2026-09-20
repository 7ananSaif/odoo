from odoo import _, api, fields, models


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    document_id = fields.Many2one('documents.document', string="Source Document", index=True)
    type = fields.Selection(
        selection_add=[('document', 'Document')],
        ondelete={'document': lambda recs: recs.write({'type': 'binary'})}
    )

    @api.depends_context('uid')
    @api.depends('document_id')
    def _compute_user_has_access(self):
        """
        Override to check if the user has access to the document.
        """
        document_sources = self.filtered(lambda s: s.type == 'document')
        for source in document_sources:
            source.user_has_access = source.document_id.user_permission != 'none'
        super(AIAgentSource, self - document_sources)._compute_user_has_access()

    def _update_name(self):
        """
        Override to update the name of the source if it is a document.
        """
        if not self:
            return

        source = self[0]

        if source.type != 'document':
            return super()._update_name()

        current_name = source.document_id.name
        if source.name != current_name:
            self.name = current_name

    def action_access_source(self):
        """
        Override to open the document if document_id exists.
        """
        self.ensure_one()
        if self.document_id:
            return {
            'type': 'ir.actions.act_window',
            'name': _('Source Document'),
            'view_mode': 'kanban',
            'res_model': 'documents.document',
            'domain': [('id', '=', self.document_id.id)],
            'view_id': self.env.ref('documents.document_view_kanban').id,
        }

        return super().action_access_source()

    def action_reprocess_index(self):
        """
        Override to reprocess the index of the sources of type document.
        """
        self.ensure_one()
        if self.type != 'document':
            return super().action_reprocess_index()

        sources_to_reprocess = self.env['ai.agent.source'].search([
            ('attachment_id.checksum', '=', self.attachment_id.checksum)
        ])

        sources_to_reprocess._update_name()

        if self.attachment_id.checksum == self.document_id.attachment_id.checksum:
            return

        self._recreate_attachments_for_sources(sources_to_reprocess)

        indexed_sources, sources_to_update_status, trigger_embeddings_cron = self._get_sources_indexing_state(
            sources_to_reprocess,
            self.document_id.attachment_id.checksum
        )

        self._update_sources_status(indexed_sources, sources_to_update_status)

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

    def _recreate_attachments_for_sources(self, sources):
        """
        Create fresh attachments for given sources, unlinking old embeddings.
        :param sources: recordset of sources to create fresh attachments for
        :type sources: ai.agent.source recordset
        """
        if not sources:
            return

        old_checksum = sources[0].attachment_id.checksum
        self.env['ai.embedding'].search([
            ('checksum', '=', old_checksum)
        ]).unlink()

        attachments_vals = []
        for source in sources:
            base_attachment = source.document_id.attachment_id.with_context(no_document=True)
            vals = base_attachment.copy_data({
                'res_model': 'ai.agent.source',
                'res_id': source.id,
            })[0]
            attachments_vals.append(vals)

        self._create_sources_attachments(sources, attachments_vals)
