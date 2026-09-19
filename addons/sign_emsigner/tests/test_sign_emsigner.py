# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from odoo.tools.misc import file_open

from odoo.addons.sign.tests.test_sign_controllers import TestSignControllerCommon


@tagged('post_install', '-at_install')
class SignEmsignerCommon(TestSignControllerCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        emsigner_auth_role = cls.env['sign.item.role'].create({
            'name': 'Emsigner Role',
            'auth_method': 'emsigner'
        })

        cls.template_emsigner = cls.env['sign.template'].create({
            'name': 'template_emsigner_test',
        })

        cls.document_emsigner = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_emsigner.id,
        })

        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_signature').id,
                'required': True,
                'responsible_id': emsigner_auth_role.id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_emsigner.id,
                'width': 0.150,
                'height': 0.015,
            }
        ])

        cls.sign_request_emsigner = cls.env['sign.request'].create({
            'template_id': cls.template_emsigner.id,
            'reference': cls.template_emsigner.display_name,
            'request_item_ids': [Command.create({
                'partner_id': cls.partner_1.id,
                'role_id': emsigner_auth_role.id,
            })],
        })

    def create_signature_value(self, sign_item_ids, role_id):
        """
        Creates a dictionary of signature values for the given sign item IDs and role ID.
        """
        with file_open('sign/static/demo/signature.png', "rb") as f:
            self.signature_fake = base64.b64encode(f.read())
        return {
            str(sign_id): self.signature_fake.decode('utf-8')
            for sign_id in sign_item_ids
            .filtered(lambda r: not r.responsible_id or r.responsible_id.id == role_id)
            .mapped('id')
        }

    def test_sign_emsigner_with_sign_is_successful(self):
        """
        Verifies that signing with valid emSigner status completes successfully.
        Ensures both request item and sign request states are updated correctly.
        """
        sign_request_item = self.sign_request_emsigner.request_item_ids[0]
        self.assertEqual(sign_request_item.state, 'sent')
        vals = self.create_signature_value(
            self.sign_request_emsigner.template_id.sign_item_ids, sign_request_item.role_id.id
        )
        sign_request_item._sign(vals, validation_required=True)
        self.assertEqual(sign_request_item.state, 'sent')
        sign_request_item.write({
            'emsigner_transaction_number': 'test1234',
            'emsigner_reference_number': 'test3232',
            'emsigner_status': 'success',
        })
        sign_request_item._post_fill_request_item()
        self.assertEqual(sign_request_item.state, 'completed')
        self.assertEqual(self.sign_request_emsigner.state, 'signed')

    def test_sign_emsigner_without_emsigner_status_raises_error(self):
        """
        Ensures that signing fails if the emSigner token or status is missing.
        verifies that a ValidationError is raised and states remain unchanged
        """
        sign_request_item = self.sign_request_emsigner.request_item_ids[0]
        self.assertEqual(sign_request_item.state, 'sent')
        vals = self.create_signature_value(
            self.sign_request_emsigner.template_id.sign_item_ids, sign_request_item.role_id.id
        )
        sign_request_item._sign(vals, validation_required=True)
        self.assertEqual(sign_request_item.state, 'sent')
        with self.assertRaises(ValidationError):
            sign_request_item._post_fill_request_item()
        self.assertEqual(sign_request_item.state, 'sent')
        self.assertEqual(self.sign_request_emsigner.state, 'sent')
