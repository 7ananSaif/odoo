# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAIEmbeddingBatching(TransactionCase):
    def _create_embedding(self, content):
        attachment = self.env["ir.attachment"].create({
            "name": f"test-{len(content)}.txt",
            "raw": b"raw",
        })
        return self.env["ai.embedding"].create({
            "attachment_id": attachment.id,
            "content": content,
            "embedding_model": "text-embedding-3-small",
        })

    def test_batches_respect_max_batch_size(self):
        """Ensure batches never exceed the configured max size."""
        embeddings = [self._create_embedding("short content") for _ in range(5)]

        with patch(
            "odoo.addons.ai.models.ai_embedding.get_embedding_config",
            return_value={"max_batch_size": 10, "max_tokens_per_request": 6},
        ):
            batches = self.env["ai.embedding"]._create_batches(embeddings, "openai")

        self.assertEqual([len(batch) for batch in batches], [2, 2, 1])

    def test_batches_split_on_token_limit(self):
        """Ensure token budget splits batches even when size allows more records."""
        embeddings = [
            self._create_embedding("a" * 8),
            self._create_embedding("b" * 12),
            self._create_embedding("c" * 12),
            self._create_embedding("d" * 4),
        ]

        with patch(
            "odoo.addons.ai.models.ai_embedding.get_embedding_config",
            return_value={"max_batch_size": 10, "max_tokens_per_request": 6},
        ):
            batches = self.env["ai.embedding"]._create_batches(embeddings, "openai")

        self.assertEqual([len(batch) for batch in batches], [2, 2])
        for batch in batches:
            token_count = sum(self.env["ai.embedding"]._estimate_tokens(emb.content) for emb in batch)
            self.assertLessEqual(token_count, 6)
