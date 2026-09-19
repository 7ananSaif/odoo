from odoo.tests import tagged
from odoo.addons.base.tests.test_ir_cron import CronMixinCase
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAIDocumentSource(TransactionCase, CronMixinCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent_a = cls.env["ai.agent"].create({"name": "Document Agent A"})
        cls.agent_b = cls.env["ai.agent"].create({"name": "Document Agent B"})

    def _create_document(self, name, content):
        attachment = self.env["ir.attachment"].create({
            "name": f"{name} Attachment",
            "raw": content,
            "mimetype": "text/plain",
        })
        return self.env["documents.document"].create({
            "name": name,
            "attachment_id": attachment.id,
        })

    def _create_sources_for_document(self, document, agents):
        sources = self.env["ai.agent.source"]
        for agent in agents:
            sources |= self.env["ai.agent.source"].create_from_attachments([document.attachment_id.id], agent.id)
        return sources

    def test_reprocess_document_source_with_unchanged_document(self):
        document = self._create_document("Doc Source", "Original content")
        source = self._create_sources_for_document(document, [self.agent_a])
        source.write({
            "status": "indexed",
            "is_active": True,
            "type": "document",
            "document_id": document.id,
        })
        previous_attachment_id = source.attachment_id.id

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers:
            source.action_reprocess_index()

        source.invalidate_recordset()

        self.assertEqual(source.attachment_id.id, previous_attachment_id, "Attachment should stay unchanged when document content is unchanged")
        self.assertEqual(source.status, "indexed")
        self.assertTrue(source.is_active)
        self.assertFalse(captured_triggers.records, "Embedding cron should not trigger without changes")

    def test_reprocess_document_source_refreshes_content_and_triggers_embeddings(self):
        document = self._create_document("Doc Source", "First version")
        sources = self._create_sources_for_document(document, [self.agent_a, self.agent_b])
        sources.write({
            "status": "indexed",
            "is_active": True,
            "type": "document",
            "document_id": document.id,
        })

        old_checksum = sources[0].attachment_id.checksum
        for source in sources:
            self.env["ai.embedding"].create({
                "attachment_id": source.attachment_id.id,
                "content": "chunk",
                "embedding_model": source.agent_id._get_embedding_model(),
            })
        new_attachment = self.env["ir.attachment"].create({
            "name": "Doc Source v2",
            "raw": b"Second version",
        })
        document.write({
            "attachment_id": new_attachment.id,
        })

        ai_generate_embedding_cron = self.env.ref("ai.ir_cron_generate_embedding").id
        with self.capture_triggers(ai_generate_embedding_cron) as captured_triggers:
            sources[:1].action_reprocess_index()

        sources.invalidate_recordset()

        self.assertTrue(
            all(source.attachment_id.checksum == document.attachment_id.checksum for source in sources),
            "All document sources should use refreshed attachments",
        )
        self.assertTrue(all(source.status == "processing" for source in sources))
        self.assertTrue(all(not source.is_active for source in sources))
        self.assertTrue(captured_triggers.records, "Embedding cron should trigger when content updates")
        self.assertFalse(self.env["ai.embedding"].search([("checksum", "=", old_checksum)]), "Old embeddings must be dropped")
        self.assertTrue(all(source.name == document.name for source in sources), "Source names should reflect the document title")
