# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict

from odoo import api, fields, models, _
from requests.exceptions import RequestException
from odoo.tools import SQL
from odoo.exceptions import UserError

from odoo.addons.ai.orm.field_vector import Vector
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai.utils.llm_providers import (
    EMBEDDING_MODELS_SELECTION,
    get_embedding_config,
    get_provider_for_embedding_model,
)

_logger = logging.getLogger(__name__)


class AIEmbedding(models.Model):
    _name = 'ai.embedding'
    _description = "Attachment Chunks Embedding"
    _order = 'sequence'

    attachment_id = fields.Many2one(
        'ir.attachment',
        string="Attachment",
        required=True,
        ondelete='cascade'
    )
    checksum = fields.Char(related='attachment_id.checksum')
    sequence = fields.Integer(string="Sequence", default=10)
    content = fields.Text(string="Chunk Content", required=True)
    embedding_model = fields.Selection(selection=EMBEDDING_MODELS_SELECTION, string="Embedding Model", required=True)
    has_embedding_generation_failed = fields.Boolean(string="Has Embedding Generation Failed", default=False)
    embedding_vector = Vector(size=1536)
    _embedding_vector_idx = models.Index("USING ivfflat (embedding_vector vector_cosine_ops)")

    @api.model
    def _get_dimensions(self):
        return self._fields['embedding_vector'].size

    @api.model
    def _get_similar_chunks(self, query_embedding, sources, embedding_model, top_n=5):
        active_sources = sources.filtered(lambda s: s.is_active)
        if not active_sources:
            return self

        attachment_ids = active_sources.mapped('attachment_id').ids
        target_checksums = self.env['ir.attachment'].browse(attachment_ids).mapped('checksum')
        # Execute the SQL query to find similar embeddings of the same sources' attachments checksum
        return self.browse(id_ for id_, *_ in self.env.execute_query(SQL(
                '''
                    SELECT
                        ai_embedding.id,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM ai_embedding
                    INNER JOIN ir_attachment ON ir_attachment.id = ai_embedding.attachment_id
                    WHERE ir_attachment.checksum = ANY(%s) AND ai_embedding.embedding_model = %s
                    ORDER BY similarity DESC
                    LIMIT %s;
                ''',
                query_embedding, target_checksums, embedding_model, top_n)
            )
        )

    @api.model
    def _cron_generate_embedding(self, batch_size=100):
        """
        Generate embeddings for sources, handling multiple embedding models per source.
        """
        # Check for sources that need to be chunked and create embedding chunks
        self._create_embedding_chunks()

        # Check for all the embedding vectors to be generated
        missing_embeddings = self.search([
            ("embedding_vector", "=", False),
            ("has_embedding_generation_failed", "=", False)
        ])

        if not missing_embeddings:
            return False
        missing_embeddings_batch = missing_embeddings[:batch_size]

        # Group by embedding model to batch similar requests
        embeddings_by_model = defaultdict(list)
        for embedding in missing_embeddings_batch:
            model = embedding.embedding_model
            embeddings_by_model[model].append(embedding)

        staged_sources = self.env['ai.agent.source'].search([
            ('attachment_id.checksum', 'in', missing_embeddings_batch.mapped('checksum'))
        ])
        _logger.info("Starting embedding update - missing %s embeddings.", len(missing_embeddings_batch))
        self.env['ir.cron']._commit_progress(remaining=len(missing_embeddings_batch))
        failed_embeddings = self.env[self._name]

        # Process each model group separately
        for model, embeddings in embeddings_by_model.items():
            provider = get_provider_for_embedding_model(self.env, model)
            # Create batches respecting provider limits
            batches = self._create_batches(embeddings, provider)
            _logger.info(
                "Processing %s embeddings for model %s in %s batches",
                len(embeddings), model, len(batches)
            )

            for batch_idx, batch in enumerate(batches):
                try:
                    _logger.info(
                        "Processing batch %s/%s with %s embeddings for model %s",
                        batch_idx + 1, len(batches), len(batch), model
                    )

                    # Prepare batch input
                    batch_content = [emb.content for emb in batch]
                    # Get embeddings for the entire batch
                    llm_service = LLMApiService(env=self.env, provider=provider)
                    response = llm_service.get_embedding(
                        input=batch_content,
                        dimensions=self._get_dimensions(),
                        model=model,
                    )
                    # Update each embedding record with its corresponding vector
                    for idx, embedding in enumerate(batch):
                        try:
                            embedding.embedding_vector = response['data'][idx]['embedding']
                        except KeyError as e:
                            _logger.error(
                                "Failed to extract embedding for record %s: %s",
                                embedding.id, str(e)
                            )
                            failed_embeddings |= embedding

                    # Commit progress for this batch
                    if not self.env['ir.cron']._commit_progress(len(batch)):
                        break

                except (RequestException, UserError) as e:
                    _logger.error(
                        "Failed to process batch %s/%s for model %s: %s",
                        batch_idx + 1, len(batches), model, str(e)
                    )
                    # Mark all embeddings in failed batch as failed
                    failed_embeddings |= self.env[self._name].concat(*batch)
                    continue

        if failed_embeddings:
            failed_embeddings.write({'has_embedding_generation_failed': True})
            self.env['ir.cron']._commit_progress(len(failed_embeddings))

        # Handle the status of sources
        for source in staged_sources:
            embedding_model = source.agent_id._get_embedding_model()
            source._update_source_status(embedding_model)

        if len(missing_embeddings) > batch_size:
            # we still have unfinished embeddings to generate: run the CRON again
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()
            return True

        return False

    def _create_embedding_chunks(self):
        """
        Create embedding chunks for sources that are processing and have an attachment
        and that don't have any embedding chunks yet
        """
        sources_to_process = self.env['ai.agent.source'].search([
            ('status', '=', 'processing'),
            ('attachment_id', '!=', False),
        ])
        if sources_to_process:
            existing_embeddings_grouped = self._read_group(
                domain=[],
                groupby=['checksum', 'embedding_model'],
            )
            existing_checksum_model_pairs = [(checksum, embedding_model) for checksum, embedding_model in existing_embeddings_grouped]
            for source in sources_to_process:
                embedding_model = source.agent_id._get_embedding_model()
                if (source.attachment_id.checksum, embedding_model) not in existing_checksum_model_pairs:
                    _logger.info("Creating embedding chunks for source %s", source.name)
                    content = source.attachment_id._get_attachment_content()
                    if not content:
                        source.write({
                            'status': 'failed',
                            'error_details': _("Invalid attachment. Failed to extract content."),
                        })
                        continue
                    source.attachment_id._setup_attachment_chunks(embedding_model, content)
                    existing_checksum_model_pairs.append((source.attachment_id.checksum, embedding_model))

    def _estimate_tokens(self, text):
        """Estimate token count based on text length.
        Based on https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
        :param text: Text to estimate tokens for
        :type text: str
        :return: Estimated token count
        :rtype: int
        """
        return len(text) // 4 if text else 0

    def _create_batches(self, embeddings, provider):
        """
        Group embeddings into batches respecting provider limits.
        :param embeddings: List of embeddings to group into batches
        :type embeddings: list[AIEmbedding]
        :param provider: Provider to use for embedding generation
        :type provider: str
        :return: List of batches
        :rtype: list[list[AIEmbedding]]
        """
        config = get_embedding_config(self.env, provider)
        max_batch_size = config['max_batch_size']
        max_tokens = config['max_tokens_per_request']

        batches = []
        current_batch = []
        current_batch_tokens = 0

        for embedding in embeddings:
            content_tokens = self._estimate_tokens(embedding.content)
            if (len(current_batch) >= max_batch_size) or \
                (current_batch_tokens + content_tokens > max_tokens):
                batches.append(current_batch)
                current_batch = []
                current_batch_tokens = 0

            current_batch.append(embedding)
            current_batch_tokens += content_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def _get_indexed_embedding_models_by_checksum(self, checksum):
        """
        Get indexed embedding models by checksum.
        :param checksum: checksum of the attachment
        :type checksum: str
        :return: list of indexed embedding models of the input checksum
        :rtype: list of str
        """
        embeddings_by_model = self._read_group(
            domain=[('checksum', '=', checksum)],
            groupby=['embedding_model'],
        )
        indexed_embedding_models = [embedding_model[0] for embedding_model in embeddings_by_model]
        return indexed_embedding_models

    @api.autovacuum
    def _gc_embeddings(self):
        """
        Autovacuum: Cleanup embedding chunks not associated with any agent's attachments.
        """
        all_agents = self.env['ai.agent'].with_context(active_test=False).search([])
        used_attachment_ids = all_agents.mapped('sources_ids').mapped('attachment_id')
        used_checksums = used_attachment_ids.mapped('checksum')
        unused_chunks = self.search([
            ('checksum', 'not in', used_checksums),
        ])
        if unused_chunks:
            chunk_count = len(unused_chunks)
            _logger.info("Autovacuum: Cleaning up %s unused embedding chunks", chunk_count)
            unused_chunks.unlink()
