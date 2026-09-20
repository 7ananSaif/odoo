from odoo import Command
from odoo.addons.documents.tests.test_documents_common import TEXT
from odoo.addons.documents.tools import attachment_read
from odoo.tests.common import TransactionCase


class TestTools(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_manager = cls.env['res.users'].create([
            {
                'email': "dtdm@yourcompany.com",
                'group_ids': [Command.link(cls.env.ref('documents.group_documents_manager').id)],
                'login': "dtdm",
                'name': "Documents Manager",
            }
        ])
        cls.document_txt = cls.env['documents.document'].create({
            'type': 'binary',
            'datas': TEXT,
            'name': 'file.txt',
            'mimetype': 'text/plain',
            'owner_id': cls.document_manager.id,
        })

    def test_attachment_read(self):
        attachment_sudo = self.document_txt.attachment_id.sudo()
        self.assertEqual(attachment_sudo.raw, b'TEST')
        self.assertEqual(attachment_read(attachment_sudo, 2), b'TE')
