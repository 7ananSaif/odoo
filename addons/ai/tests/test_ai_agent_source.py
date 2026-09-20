# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAIAgentSource(TransactionCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent = cls.env["ai.agent"].create({
            "name": "Agent Source Tests",
        })

    def _create_url_source(self, name, url, status="indexed", is_active=True, attachment_content="old content"):
        source = self.env["ai.agent.source"].create({
            "name": name,
            "agent_id": self.agent.id,
            "type": "url",
            "url": url,
        })
        if attachment_content is not None:
            attachment = self.env["ir.attachment"].create({
                "name": f"{name} attachment",
                "res_model": "ai.agent.source",
                "res_id": source.id,
                "raw": attachment_content,
                "index_content": attachment_content,
                "mimetype": "text/html",
                "url": url,
            })
            source.attachment_id = attachment.id

        source.write({
            "status": status,
            "is_active": is_active,
        })
        return source

    def test_reprocess_sets_sources_processing_and_triggers_scrape_cron(self):
        url = "https://example.com/article"
        ai_process_sources_cron = self.env.ref('ai.ir_cron_process_sources').id
        source_a = self._create_url_source("Source A", url, status="indexed", is_active=True, attachment_content="<p>Old</p>")
        source_b = self._create_url_source("Source B", url, status="indexed", is_active=True, attachment_content="<p>Old</p>")

        with self.capture_triggers(ai_process_sources_cron) as captured_triggers, \
                patch("odoo.addons.ai.models.ai_agent_source.AIAgentSource._get_name_from_url", return_value="Updated title"):
            source_a.action_reprocess_index()

        source_a.invalidate_recordset()
        source_b.invalidate_recordset()

        self.assertEqual(source_a.status, "processing")
        self.assertEqual(source_b.status, "processing")
        self.assertFalse(source_a.is_active)
        self.assertFalse(source_b.is_active)
        self.assertEqual(source_a.name, "Updated title")
        self.assertEqual(source_b.name, "Updated title")
        self.assertTrue(len(captured_triggers.records))

    def test_scraping_cron_refreshes_processing_sources_and_schedules_embeddings(self):
        url = "https://example.com/article"
        processing_source = self._create_url_source(
            "Needs Refresh", url, status="processing", is_active=False, attachment_content=None,
        )
        indexed_source = self._create_url_source(
            "Indexed Copy", url, status="indexed", is_active=True, attachment_content="<p>Old</p>",
        )

        fresh_content = "<p>Fresh content</p>"
        ai_generate_embedding_cron = self.env.ref('ai.ir_cron_generate_embedding').id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                patch("odoo.addons.ai.models.ai_agent_source.AIAgentSource._fetch_content", return_value={"content": fresh_content}):
            self.env["ai.agent.source"]._cron_process_sources()

            processing_source.invalidate_recordset()
            indexed_source.invalidate_recordset()

            self.assertTrue(processing_source.attachment_id, "Processing source should now have a fresh attachment")
            self.assertEqual(processing_source.attachment_id.index_content, fresh_content)
            self.assertEqual(indexed_source.attachment_id.index_content, fresh_content)
            self.assertEqual(indexed_source.status, "processing")
            self.assertFalse(indexed_source.is_active)

            self.assertTrue(len(captured_triggers_embedding.records))
            self.assertEqual(captured_triggers_embedding.records[0].cron_id, self.env.ref('ai.ir_cron_generate_embedding'))

    def test_scraping_cron_marks_sources_failed_on_fetch_error(self):
        url = "https://example.com/failure"
        failing_source_a = self._create_url_source(
            "failing source a", url, status="processing", is_active=False, attachment_content="<p>Old</p>",
        )
        failing_source_b = self._create_url_source(
            "failing source b", url, status="processing", is_active=False, attachment_content="<p>Old</p>",
        )

        ai_generate_embedding_cron = self.env.ref('ai.ir_cron_generate_embedding').id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                patch("odoo.addons.ai.models.ai_agent_source.AIAgentSource._fetch_content", return_value={"content": None, "error": "Fetch failed"}):
            self.env["ai.agent.source"]._cron_process_sources()

            failing_source_a.invalidate_recordset()
            failing_source_b.invalidate_recordset()

            self.assertEqual(failing_source_a.status, "failed")
            self.assertEqual(failing_source_b.status, "failed")
            self.assertFalse(failing_source_a.is_active)
            self.assertFalse(failing_source_b.is_active)
            self.assertEqual(failing_source_a.error_details, "Fetch failed")
            self.assertEqual(failing_source_b.error_details, "Fetch failed")
            self.assertFalse(len(captured_triggers_embedding.records), "Embedding cron should not trigger on fetch failure")

    def test_scraping_cron_unlinks_embeddings_when_content_changes(self):
        url = "https://example.com/refresh"
        source = self._create_url_source(
            "Refresh Needed", url, status="processing", is_active=False, attachment_content="<p>Old</p>",
        )
        embedding_model = source.agent_id._get_embedding_model()
        embedding = self.env["ai.embedding"].create({
            "attachment_id": source.attachment_id.id,
            "content": "chunk content",
            "embedding_model": embedding_model,
        })

        updated_content = "<p>Updated content</p>"
        ai_generate_embedding_cron = self.env.ref('ai.ir_cron_generate_embedding').id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers_embedding, \
                patch("odoo.addons.ai.models.ai_agent_source.AIAgentSource._fetch_content", return_value={"content": updated_content, "title": "Updated title"}):
            self.env["ai.agent.source"]._cron_process_sources()

            source.invalidate_recordset()

            self.assertEqual(source.attachment_id.index_content, updated_content)
            self.assertTrue(len(captured_triggers_embedding.records), "Embedding cron should trigger when content changes")
            self.assertFalse(self.env["ai.embedding"].browse(embedding.id).exists(), "Embeddings linked to outdated attachments must be removed")
