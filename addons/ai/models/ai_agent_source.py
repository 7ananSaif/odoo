# Part of Odoo. See LICENSE file for full copyright and licensing details.
import requests
from collections import defaultdict


from odoo import _, api, fields, models
from odoo.addons.mail.tools import link_preview
from odoo.exceptions import AccessError

from ..utils.html_extractor import HTMLExtractor


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _description = 'AI Agent Source'
    _order = 'name'

    name = fields.Char(string="Name")
    agent_id = fields.Many2one('ai.agent', string="Agent", index=True, required=True)
    type = fields.Selection([('url', 'URL'), ('binary', 'File')],
                    default='binary', string='Type', required=True, readonly=True)

    status = fields.Selection(string="Status", selection=[('processing', 'Processing'), ('indexed', 'Indexed'), ('failed', 'Failed')], default='processing')
    is_active = fields.Boolean(string="Active", help="If the source is active, it will be used in the RAG context.")
    error_details = fields.Text(string="Error Details", readonly=True)

    attachment_id = fields.Many2one('ir.attachment', string="Attachment", index=True, ondelete='cascade')
    mimetype = fields.Char(related='attachment_id.mimetype')
    file_size = fields.Integer(related='attachment_id.file_size')

    url = fields.Char(string="URL")

    user_has_access = fields.Boolean(compute="_compute_user_has_access", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        sources = super().create(vals_list)
        trigger_embeddings_cron = False
        trigger_scrape_urls_cron = False
        for source in sources:
            if source.attachment_id:
                source.attachment_id.write({
                    'res_model': 'ai.agent.source',
                    'res_id': source.id,
                })
            if source.type == 'binary' and source.status == 'processing':
                trigger_embeddings_cron = True
            elif source.type == 'url':
                trigger_scrape_urls_cron = True

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()
        if trigger_scrape_urls_cron:
            self.env.ref('ai.ir_cron_process_sources')._trigger()

        return sources

    @api.model
    def create_from_attachments(self, attachment_ids, agent_id):
        """
        Create AI agent sources from existing attachments.

        :param attachment_ids: list of attachment IDs
        :type attachment_ids: list of int
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        checksums = attachments.mapped('checksum')
        agent = self.env['ai.agent'].browse(agent_id)
        embedding_model = agent._get_embedding_model()
        existing_checksums = set(
            self.env['ai.embedding'].search([('checksum', 'in', checksums), ('embedding_model', '=', embedding_model)]).mapped('checksum')
        )
        # Filter attachments that already have embeddings using their checksum
        matching_attachments = attachments.filtered(lambda a: a.checksum in existing_checksums)

        vals_list = []
        for attachment in attachments:
            source = {
                'name': attachment.name,
                'agent_id': agent_id,
                'attachment_id': attachment.id,
                'type': 'binary',
            }
            if attachment in matching_attachments:
                source['status'] = 'indexed'
                source['is_active'] = True

            vals_list.append(source)

        return self.create(vals_list)

    @api.model
    def create_from_binary_files(self, files_datas, agent_id):
        """
        Create AI agent sources from binary records.
        :param records: list of records with name and datas
        :type records: list of dicts
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        attachment_ids = self.env['ir.attachment'].create(files_datas).ids
        return self.create_from_attachments(attachment_ids, agent_id)

    @api.model
    def create_from_urls(self, urls, agent_id):
        """
        Create AI agent sources from URLs.

        :param urls: list of urls
        :type urls: list of str
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        if not urls:
            return self.browse()

        if not self.env.is_system():
            raise AccessError(_('Only administrators can create sources from URLs.'))

        request_session = requests.Session()
        vals_list = []
        for url in urls:
            name = self._get_name_from_url(url, request_session)
            url_source = {
                'name': name,
                'url': url,
                'agent_id': agent_id,
                'type': 'url',
            }
            vals_list.append(url_source)

        return self.create(vals_list)

    @api.model
    def _get_name_from_url(self, url, session):
        """
        Get the name of the source from the URL.
        :param url: URL to get the name from
        :type url: str
        :param session: request session
        :type session: requests.Session
        :return: name of the source
        :rtype: str
        """
        preview = link_preview.get_link_preview_from_url(url, session)
        if preview and preview.get('og_title'):
            return preview['og_title']
        return url

    @api.ondelete(at_uninstall=False)
    def _unlink_attachments(self):
        """Delete attachments when a source is deleted."""
        for source in self:
            if source.attachment_id:
                source.attachment_id.unlink()

    @api.depends_context('uid')
    @api.depends('attachment_id')
    def _compute_user_has_access(self):
        """
        Compute user access by delegating to the underlying source.
        Overriden in ai_documents and ai_knowledge.
        """
        self.filtered(lambda s: s.type == 'binary').user_has_access = self.env.user._is_internal()
        self.filtered(lambda s: s.type == 'url').user_has_access = True

    def _get_source_embeddings_status(self, embedding_model):
        """
        Get the current embedding status for a source with the given model.

        :param embedding_model: embedding model
        :type embedding_model: str
        :return: dict with status info
        :rtype: dict
        """
        self.ensure_one()

        # Get all embeddings for this source
        checksum = self.attachment_id.checksum
        embedding_chunks = self.env['ai.embedding'].search([
            ('checksum', '=', checksum),
            ('embedding_model', '=', embedding_model)
        ])

        if not embedding_chunks:
            return {'has_chunks': False}

        failed_count = embedding_chunks.filtered('has_embedding_generation_failed')
        missing_vectors = embedding_chunks.filtered(lambda e: not e.embedding_vector)

        return {
            'has_chunks': True,
            'has_failed': bool(failed_count),
            'has_missing': bool(missing_vectors),
        }

    def _update_source_status(self, embedding_model):
        """
        Update source status based on current embedding state.

        :param embedding_model: embedding model
        :type embedding_model: str
        :return: True if source status was updated, False otherwise
        :rtype: bool
        """
        self.ensure_one()
        embedding_info = self._get_source_embeddings_status(embedding_model)

        if not embedding_info['has_chunks']:
            # No chunks exist, it needs to be processed first
            return False

        elif embedding_info.get('has_failed'):
            self.write({
                'status': 'failed',
                'is_active': False,
                'error_details': _("Embedding generation failed using the current LLM model selected."),
            })

        elif embedding_info.get('has_missing'):
            self.write({
                'status': 'processing',
                'is_active': False,
                'error_details': False,
            })

        else:
            # Has chunks and no missing vectors, it's ready to be used
            self.write({
                'status': 'indexed',
                'is_active': True,
                'error_details': False,
            })

        return True

    def _sync_new_agent_provider(self, embedding_model):
        """
        Sync sources when embedding model changes.

        :param embedding_model: embedding model
        :type embedding_model: str
        """
        sources_to_process = self.env[self._name]
        for source in self:
            can_update = source._update_source_status(embedding_model)
            # If the source can't be updated and it has an attachment, it means it has no chunks,
            # so we need to process it first
            if not can_update and source.attachment_id:
                source.write({
                    'status': 'processing',
                    'is_active': False,
                    'error_details': False,
                })
                sources_to_process |= source

        if sources_to_process:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

    def action_retry_failed_source(self):
        """
        Retry failed sources by deleting the source chunks and re-triggering the appropriate cron job.
        """
        self.ensure_one()
        if self.status == 'failed':
            source_chunks = self.env['ai.embedding'].search([('checksum', '=', self.attachment_id.checksum), ('embedding_model', '=', self.agent_id._get_embedding_model())])
            if source_chunks:
                source_chunks.unlink()

            if self.url:
                cron = 'ai.ir_cron_process_sources'
            elif self.attachment_id:
                cron = 'ai.ir_cron_generate_embedding'
            else:
                cron = False

            if cron:
                self.write({
                    'status': 'processing',
                    'is_active': False,
                    'error_details': False,
                })

                self.env.ref(cron)._trigger()

    def action_open_sources_dialog(self):
        """
        Open the add sources dialog.
        """
        agent_id = self.env.context.get('agent_id')
        return {
            "type": "ir.actions.client",
            "tag": "ai_open_sources_dialog",
            "params": {
                "agent_id": agent_id,
            }
        }

    def action_access_source(self):
        """
        Access the source content. Overriden in ai_documents and ai_knowledge.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.url or f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'new',
        }

    def action_reprocess_index(self):
        """
        Reprocess the index of the source.
        """
        self.ensure_one()
        sources_to_reprocess = self.env['ai.agent.source'].search([
            ('attachment_id.checksum', '=', self.attachment_id.checksum)
        ])
        sources_to_reprocess.write({
            'status': 'processing',
            'is_active': False,
        })
        sources_to_reprocess._update_name()
        self.env.ref('ai.ir_cron_process_sources')._trigger()

    def _update_name(self):
        """
        Update the name of the source if needed.
        To be Overriden.
        """
        if not self:
            return

        source = self[0]
        if source.type == 'url':
            request_session = requests.Session()
            current_name = self._get_name_from_url(source.url, request_session)
            if source.name != current_name:
                self.name = current_name

    def _cron_process_sources(self):
        """
        Scrape and process all sources that require content retrieval.
        This method fetches the latest content for each source, then creates
        or updates the corresponding attachments.
        """
        sources_to_process = self._get_sources_to_process()
        if not sources_to_process:
            return

        # Group sources by URL to process them
        sources_by_url = defaultdict(lambda: self.env['ai.agent.source'])
        for source in sources_to_process:
            sources_by_url[source.url] |= source

        trigger_embeddings_cron = False
        if sources_by_url:
            trigger_embeddings_cron = self._process_sources_content(sources_by_url)

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

    def _get_sources_to_process(self):
        """
        Get the sources to process.
        Default for URL sources.
        To be Overriden.
        :return: sources to process
        :rtype: ai.agent.source recordset
        """
        target_urls = self.env['ai.agent.source'].search([
            ('type', '=', 'url'),
            ('status', '=', 'processing'),
        ]).mapped('url')

        sources_to_process = self.env['ai.agent.source'].search([
            ('url', 'in', target_urls),
        ])

        return sources_to_process

    def _fetch_content(self, source):
        """
        Fetch the content of a url source.
        Default for URL sources.
        To be Overriden.
        :param source: source to fetch the content from
        :type source: ai.agent.source record
        :return: dictionary with 'content', 'title', and 'error' keys, or None
        :rtype: dict or None
        """
        if source.type == 'url' and source.url:
            extractor = HTMLExtractor()
            result = extractor.scrap(source.url)
            if not result or not result['content']:
                return {"content": None, "error": result.get('error', _("Failed to fetch the content of the source."))}
            return result
        return {'error': _("Failed to fetch the content of the source.")}

    def _get_sources_indexing_state(self, sources, updated_checksum):
        """
        Determine the sources' embedding and indexing state.
        :param sources: recordset of sources to determine the state
        :type sources: ai.agent.source recordset
        :param updated_checksum: checksum of the updated content
        :type updated_checksum: str
        :return: tuple of (indexed_sources, sources_to_update_status)
        :rtype: tuple
        """
        indexed_embedding_models = self.env['ai.embedding']._get_indexed_embedding_models_by_checksum(updated_checksum)

        indexed_sources = sources.filtered(lambda source: source.agent_id._get_embedding_model() in indexed_embedding_models)
        non_indexed_sources = sources - indexed_sources
        sources_to_update_status = non_indexed_sources.filtered(lambda source: source.status != 'processing')
        trigger_embeddings_cron = bool(non_indexed_sources)

        return indexed_sources, sources_to_update_status, trigger_embeddings_cron

    def _update_sources_status(self, indexed_sources, processing_sources, failed_by_error=None):
        """
        Update sources' status based on embedding availability.
        :param indexed_sources: recordset of indexed sources
        :type indexed_sources: ai.agent.source recordset
        :param processing_sources: recordset of processing sources
        :type processing_sources: ai.agent.source recordset
        :param failed_by_error: dictionary mapping error messages to sources
        :type failed_by_error: dict
        """
        if indexed_sources:
            indexed_sources.write({
                'status': 'indexed',
                'is_active': True,
            })

        if processing_sources:
            processing_sources.write({
                'status': 'processing',
                'is_active': False,
            })

        if failed_by_error:
            for error_msg, sources in failed_by_error.items():
                sources.write({
                    'status': 'failed',
                    'is_active': False,
                    'error_details': error_msg,
                })

    def _create_sources_attachments(self, sources, attachments_vals):
        """
        Create attachments for sources.
        :param sources: recordset of sources to create attachments for
        :type sources: ai.agent.source recordset
        :param attachments_vals: list of dictionaries with attachment values
        :type attachments_vals: list of dicts
        """
        new_attachments = self.env['ir.attachment'].create(attachments_vals)
        for source, new_attachment in zip(sources, new_attachments):
            source.attachment_id = new_attachment.id

    def _process_sources_content(self, sources_by_url):
        """
        Process source content and create/update their attachments.
        :param sources_by_url: dictionary mapping URLs to sources recordsets
        :type sources_by_url: dict
        :return: True if embeddings need to be generated, False otherwise
        :rtype: bool
        """
        trigger_embeddings_cron = False
        indexed_sources = self.env['ai.agent.source']
        sources_to_update_status = self.env['ai.agent.source']
        attachments_embeddings_to_unlink = self.env['ir.attachment']
        failed_by_error = defaultdict(lambda: self.env['ai.agent.source'])

        for url, url_sources in sources_by_url.items():
            # Fetch content from a single representative source
            result = self._fetch_content(url_sources[0])
            if not result or not result['content']:
                failed_by_error[result['error']] |= url_sources
                continue

            updated_content = result['content'].encode()
            updated_content_checksum = self.env['ir.attachment']._compute_checksum(updated_content)

            # Check for the new sources to attach
            sources_to_attach = url_sources.filtered(lambda s: not s.attachment_id)
            attachment_vals_list = []
            for source in sources_to_attach:
                attachment_vals_list.append({
                    'name': f"{source.name}-({url})",
                    'res_model': 'ai.agent.source',
                    'res_id': source.id,
                    'raw': updated_content,
                    'mimetype': 'text/html',
                    'url': url,
                })

            if attachment_vals_list:
                self._create_sources_attachments(sources_to_attach, attachment_vals_list)

            # Check for any sources with outdated attachments content or not indexed
            attachments_to_update = url_sources.filtered(lambda source: source.attachment_id.checksum != updated_content_checksum).mapped('attachment_id')
            attachments_embeddings_to_unlink |= attachments_to_update

            url_indexed_sources, url_sources_to_update_status, url_trigger_embeddings_cron = self._get_sources_indexing_state(url_sources, updated_content_checksum)
            indexed_sources |= url_indexed_sources
            sources_to_update_status |= url_sources_to_update_status
            trigger_embeddings_cron |= url_trigger_embeddings_cron

            if attachments_to_update:
                attachments_to_update.write({
                    'raw': updated_content,
                })

        if attachments_embeddings_to_unlink:
            self.env['ai.embedding'].search([
                ('attachment_id', 'in', attachments_embeddings_to_unlink.ids)
            ]).unlink()

        self._update_sources_status(indexed_sources, sources_to_update_status, failed_by_error)

        return trigger_embeddings_cron
