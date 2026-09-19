# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError, UserError
from odoo.tools import file_open, mute_logger
from odoo.tests import tagged, freeze_time
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestSignTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with file_open('sign/static/demo/sample_contract.pdf', "rb") as f:
            cls.pdf_data = base64.b64encode(f.read())
        with file_open('mail/tests/discuss/files/test_AES.pdf', "rb") as f:
            cls.AES_pdf_data = base64.b64encode(f.read())
        with file_open('mail/tests/discuss/files/test_unicode.pdf', "rb") as f:
            cls.unicode_pdf_data = base64.b64encode(f.read())

        cls.test_user = new_test_user(cls.env,
                                      "test_user_1",
                                      email="test_user_1@nowhere.com",
                                      password="test_user_1",
                                      tz="UTC",
                                      groups='sign.group_sign_user')

    def test_create_update_copy_unlink_template(self):
        # create
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}])
        sign_template_id, name = res.get('id', 0), res.get('name', '')
        sign_template = self.env['sign.template'].with_user(self.test_user).browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        document = self.env['sign.document'].browse(document_id)
        self.assertTrue(sign_template.exists(), 'The template should be created')
        self.assertTrue(sign_template.document_ids.exists(), 'The template should be created')
        self.assertEqual(name, 'sample_contract.pdf', 'The name of the template should be sample_contract.pdf')

        # update
        result = sign_template.update_from_pdfviewer(sign_items={'-1': {
                'type_id': self.env.ref('sign.sign_item_type_text').id,
                'name': 'employee_id.name',
                'required': True,
                'responsible_id': self.env.ref('sign.sign_item_role_default').id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'template_id': sign_template_id,
                'document_id': document_id,
                'width': 0.150,
                'height': 0.015,
                'transaction_id': -1,
            }, '-2': {
                'type_id': self.env.ref('sign.sign_item_type_text').id,
                'name': 'employee_id.name',
                'required': True,
                'responsible_id': self.env.ref('sign.sign_item_role_default').id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'template_id': sign_template_id,
                'document_id': document_id,
                'width': 0.150,
                'height': 0.015,
                'transaction_id': -2,
            }}, name='')
        self.assertEqual(len(sign_template.sign_item_ids), 2, 'The template should have 2 sign.item')
        self.assertTrue(result.get('-1', 0) > 0 and result.get('-2', 0) > 0, 'An id mapping should be returned')
        self.assertEqual(set(sign_template.sign_item_ids.ids), set(result.values()), 'An id mapping should be returned')
        self.assertEqual(document.name, 'sample_contract.pdf', 'The name of the document should be sample_contract.pdf')
        sign_template.update_from_pdfviewer(deleted_sign_item_ids=[sign_template.sign_item_ids[0].id], name='sample_contract2.pdf', document_id=document_id)
        self.assertEqual(len(sign_template.sign_item_ids), 1, 'The template should have 1 sign.item')
        self.assertEqual(document.name, 'sample_contract2.pdf', 'The name of the document should be sample_contract2.pdf')

        # copy
        copy_name = sign_template._get_copy_name(sign_template.name)
        self.assertNotEqual(sign_template.name, copy_name, 'The copy name should not equal to the original one')
        sign_template_copy = sign_template.copy()
        self.assertEqual(sign_template_copy.name, copy_name, 'The name of the copied template should be decided by the _get_copy_name method')
        self.assertEqual(len(sign_template.sign_item_ids), 1, 'The copied template should have 1 sign.item')

        # unlink
        sign_item = sign_template.sign_item_ids[0]
        sign_document = sign_template.document_ids[0]
        sign_template.unlink()
        self.assertFalse(sign_item.exists(), 'The sign_item should be deleted')
        self.assertFalse(sign_document.exists(), 'The document should be deleted')

    def test_update_from_pdfviewer_bad_internet(self):
        # create
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}])
        sign_template_id = res.get('id', 0)
        sign_template = self.env['sign.template'].with_user(self.test_user).browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        # add new sign items
        # A client creates a new item1(-1)
        result1 = sign_template.update_from_pdfviewer(sign_items={'-1': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.058,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -1,
            'document_id': document_id,
        }})
        item1_id = result1.get('-1', 0)
        self.assertEqual(len(sign_template.sign_item_ids), 1, 'The template should have 1 sign.item')
        self.assertEqual(set(result1.keys()), set(['-1']), 'An id mapping should be returned')
        self.assertEqual(set(sign_template.sign_item_ids.ids), set([item1_id]), 'An id mapping should be returned')
        self.assertEqual(self.env['sign.item'].browse(item1_id).posY, 0.058, 'The poxY of item1 should be 0.058')

        # result1 is received by client
        # The client creates new item2(-2) and item3(-3), and updates the posY of item1
        result2 = sign_template.update_from_pdfviewer(sign_items={str(item1_id): {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': 0,
            'document_id': document_id,
        }, '-2': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.258,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -2,
            'document_id': document_id,
        }, '-3': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.358,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -3,
            'document_id': document_id,
        }})
        self.assertEqual(set(result2.keys()), set(['-2', '-3']), 'An id mapping should be returned')
        self.assertEqual(set(sign_template.sign_item_ids.ids), set(list(result2.values()) + [item1_id]), 'An id mapping should be returned')
        self.assertEqual(self.env['sign.item'].browse(item1_id).posY, 0.158, 'The poxY of item1 should be 0.158')

        # Result2 is not received by the client / the client sends another rpc call before it receive the result2
        # The client removes the item3(-3) and create a new item4(-4) and update the posY of item2(-2)
        result3 = sign_template.update_from_pdfviewer(sign_items={str(item1_id): {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.158,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': 0,
            'document_id': document_id,
        }, '-2': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.298,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -2,
            'document_id': document_id,
        }, '-4': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'page': 1,
            'posX': 0.273,
            'posY': 0.458,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -4,
            'document_id': document_id,
        }}, deleted_sign_item_ids=[-3])
        item2_id = result3.get('-2', 0)
        self.assertEqual(set(result3.keys()), set(['-2', '-4']), 'An id mapping should be returned')
        self.assertEqual(set(sign_template.sign_item_ids.ids), set(list(result3.values()) + [item1_id]), 'An id mapping should be returned')
        self.assertEqual(self.env['sign.item'].browse(item1_id).posY, 0.158, 'The poxY of item1 should be 0.158')
        self.assertEqual(self.env['sign.item'].browse(item2_id).posY, 0.298, 'The poxY of item2 should be 0.298')

    def test_sign_item_has_proper_type(self):
        """Tests that a sign item can only be set as read-only if it has certain types."""
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}])
        sign_template_id = res.get('id', 0)
        sign_template = self.env['sign.template'].with_user(self.test_user).browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        for item_type in ('signature', 'initial', 'radio', 'checkbox', 'selection'):
            with self.subTest(f'Create sign item of type {item_type}'):
                with self.assertRaisesRegex(ValidationError, "Read-only can only be applied to items of the following types: 'Text', 'Name', 'Email', 'Phone', 'Company', 'Multiline', 'Date', 'Strikethrough'"):
                    type_id = self.env["sign.item.type"].create({
                        'name': item_type,
                        'item_type': item_type
                    })
                    self.env["sign.item"].create({
                        'template_id': sign_template_id,
                        'document_id': document_id,
                        'type_id': type_id.id,
                        'name': 'employee_id.name',
                        'required': False,
                        'constant': True,
                        'responsible_id': self.env.ref('sign.sign_item_role_default').id,
                        'page': 1,
                        'posX': 0.273,
                        'posY': 0.458,
                        'width': 0.150,
                        'height': 0.015,
                        'transaction_id': -4,
                    })

    def test_sign_item_model_name(self):
        """ Make sure that we can't save a model on sign.template that is incompatible with the sign items """
        # Use models that are available in the sign application
        model_sr = self.env['ir.model']._get('sign.request')
        model_cron = self.env['ir.model']._get('ir.cron')
        model_partner = self.env['ir.model']._get('res.partner')
        type_request = self.env["sign.item.type"].create({
                        'name': "SR field",
                        'item_type': 'text',
                        'model_id': model_sr.id,
                        'auto_field': 'reference',

        })
        type_partner = self.env["sign.item.type"].create({
                        'name': "Partner field",
                        'item_type': 'text',
                        'model_id': model_partner.id,
                        'auto_field': 'partner_latitude',

        })
        type_cron = self.env["sign.item.type"].create({
                        'name': "Cron field",
                        'item_type': 'text',
                        'model_id': model_cron.id,
                        'auto_field': 'interval_type',

        })
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}])
        sign_template_id = res.get('id', 0)
        sign_template = self.env['sign.template'].with_user(self.test_user).browse(sign_template_id)
        document_id = sign_template.document_ids[0].id
        for sign_type in [type_request, type_partner, type_cron]:
            self.env["sign.item"].create({
                'template_id': sign_template_id,
                'document_id': document_id,
                'type_id': sign_type.id,
                'name': 'employee_id.name',
                'required': False,
                'constant': True,
                'responsible_id': self.env.ref('sign.sign_item_role_default').id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.458,
                'width': 0.150,
                'height': 0.015,
                'transaction_id': -4,
            })
        with self.assertRaises(UserError):
            sign_template.model_id = type_request.id
        with self.assertRaises(UserError):
            sign_template.model_id = type_cron.id

    @mute_logger('odoo.addons.sign.utils.pdf_handling')
    def test_invalid_pdf_upload(self):
        """ Make sure that uploading invalid/encrypted PDF upload should raise the error. """
        for fname, data in [('test_AES.pdf', self.AES_pdf_data), ('test_unicode.pdf', self.unicode_pdf_data)]:
            with self.subTest(fname=fname):
                with self.assertRaises(ValidationError):
                    self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
                        attachment_data_list=[{'name': fname, 'datas': data}]
                    )

    @mute_logger('odoo.addons.sign.utils.pdf_handling', 'pypdf._reader')
    def test_invalid_pdf_add_in_document(self):
        """ Make sure that adding invalid/encrypted PDF in Document should raise the error. """
        # create a valid template first
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}]
        )
        template_id = self.env['sign.template'].with_user(self.test_user).browse(res.get('id', 0))
        self.assertEqual(len(template_id.document_ids), 1)

        for fname, data in [('test_AES.pdf', self.AES_pdf_data), ('test_unicode.pdf', self.unicode_pdf_data)]:
            with self.subTest(fname=fname):
                with self.assertRaises(ValidationError):
                    template_id.update_from_attachment_data(attachment_data_list=[{'name': fname, 'datas': data}])

    def test_update_document_preserves_sign_items(self):
        """ Ensure that updating a document in a sign template creates a new template and preserves sign items. """
        # Create a template with one document and one sign item
        res = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}]
        )
        template_id = res.get('id', 0)
        template = self.env['sign.template'].with_user(self.test_user).browse(template_id)
        document = template.document_ids[0]
        self.env['sign.item'].create({
            'template_id': template.id,
            'document_id': document.id,
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'employee_id.name',
            'required': True,
            'responsible_id': self.env.ref('sign.sign_item_role_default').id,
            'transaction_id': -1, 'page': 1,
            'posX': 0.273, 'posY': 0.158, 'width': 0.150, 'height': 0.015,
        })
        self.assertEqual(len(template.sign_item_ids), 1, 'Template should have 1 sign item before replacement')

        # Prepare new document data, call update_document, get the new template and perform the checks.
        new_attachment_data = {'name': 'new_contract.pdf', 'datas': self.pdf_data}
        action = template.update_document(document.id, new_attachment_data)
        new_template_id = action['params']['id']
        new_template = self.env['sign.template'].browse(new_template_id)
        self.assertTrue(any(doc.name == 'new_contract.pdf' for doc in new_template.document_ids), 'New template should have the new document')
        self.assertEqual(len(new_template.sign_item_ids), 1, 'Sign items should be preserved in the new template')

    def _get_signer_and_item_gc_context(self, sign_template):
        all_signer_ids = self.env['sign.item'].search([]).mapped('responsible_id.id')
        active_signer_ids = self.env['sign.item'].search([
            ('page', '>', -1)
        ]).mapped('responsible_id.id')
        template_active_signer_ids = sign_template.sign_item_ids.mapped('responsible_id.id')
        signers_without_item_ids = self.env['sign.item.role'].search([
            ('id', 'in', all_signer_ids),
            ('id', 'not in', active_signer_ids)
        ]).ids
        non_active_item_ids = self.env['sign.item'].search([('page', '<', 0)]).ids

        return all_signer_ids, template_active_signer_ids, signers_without_item_ids, non_active_item_ids

    def test_gc_removes_orphan_roles_and_dummy_items(self):
        sign_template_id = self.env['sign.template'].with_user(self.test_user).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data}])['id']
        sign_template = self.env['sign.template'].with_user(self.test_user).browse(sign_template_id)
        document_id = sign_template.document_ids[0].id

        signers_with_items = []
        signers_without_item = []
        signers_with_items.append(sign_template.create_item_and_role(document_id, 'Signer1'))
        signer1_item_id = sign_template.update_from_pdfviewer(sign_items={'-1': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'Signer1',
            'required': True,
            'responsible_id': signers_with_items[-1],
            'page': 1,
            'posX': 0.273,
            'posY': 0.058,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -1,
            'document_id': document_id,
        }})['-1']

        signers_with_items.append(sign_template.create_item_and_role(document_id, 'Signer2'))
        signer2_item_id = sign_template.update_from_pdfviewer(sign_items={'-2': {
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'name': 'Signer2',
            'required': True,
            'responsible_id': signers_with_items[-1],
            'page': 1,
            'posX': 0.273,
            'posY': 0.058,
            'width': 0.150,
            'height': 0.015,
            'transaction_id': -1,
            'document_id': document_id,
        }})['-2']

        signers_without_item.append(sign_template.create_item_and_role(document_id, 'Signer3'))
        signers_without_item.append(sign_template.create_item_and_role(document_id, 'Signer4'))

        all_signer_ids, template_active_signer_ids, signers_without_item_ids, non_active_item_ids \
            = self._get_signer_and_item_gc_context(sign_template)

        self.assertTrue(set(signers_with_items + signers_without_item).issubset(set(all_signer_ids)),
                        "The signers created is not in the database.")
        self.assertEqual(set(signers_with_items), set(template_active_signer_ids),
                         "The loaded signers in template should only be the signers with active sign item.")
        self.assertEqual(set(signers_without_item), set(signers_without_item_ids),
                         "The signers without active item in the database is not equal to the one created.")
        self.assertEqual({signer1_item_id, signer2_item_id}, set(sign_template.sign_item_ids.ids),
                         "The loaded sign items in the template should only be the active items.")
        self.assertEqual(len(non_active_item_ids), 4,
                         "The number of non-active sign items should equal to 4.")

        garbage_collecting_time = fields.Datetime.now() + timedelta(days=1, minutes=1)
        with freeze_time(garbage_collecting_time):
            sign_template._gc_sign_items()
            self.env.flush_all()
            self.cr.flush()

            all_signer_ids, template_active_signer_ids, signers_without_item_ids, non_active_item_ids \
                = self._get_signer_and_item_gc_context(sign_template)

            self.assertTrue(set(signers_with_items).issubset(set(all_signer_ids)),
                            "Signers with active item should be a subset of all signers in the database after autovacuum.")
            self.assertFalse(set(signers_without_item).issubset(set(all_signer_ids)),
                            "Signers without active item should not be a subset of all signers in the database after autovacuum.")
            self.assertEqual(set(signers_with_items), set(template_active_signer_ids),
                             "The loaded signers in template should still be the same after autovacuum.")
            self.assertEqual(len(signers_without_item_ids), 0,
                             "Signers without active item should be deleted after autovacuum.")
            self.assertEqual({signer1_item_id, signer2_item_id}, set(sign_template.sign_item_ids.ids),
                             "The loaded sign items in the template should only be the active items.")
            self.assertEqual(len(non_active_item_ids), 0,
                             "The number of non-active sign items should equal to 0 after autovacuum.")
