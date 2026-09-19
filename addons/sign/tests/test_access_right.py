# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .sign_request_common import SignRequestCommon

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import new_test_user


class TestAccessRight(SignRequestCommon):

    def test_update_item_partner(self):
        self.role_signer_1.change_authorized = True
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2,
                                                                signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in
                                       sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        # We update the item partner with a non-privileged sign user.
        sign_request_item_signer_1.with_user(self.user_1).partner_id = self.partner_5
        # reassign
        self.assertEqual(sign_request_item_signer_1.signer_email, "char.aznable.a@example.com", 'email address should be char.aznable.a@example.com')

    def test_user_can_edit_only_own_templates_and_documents(self):
        """ Ensure basic sign users can only edit their own templates and documents. """
        res = self.env['sign.template'].with_user(self.user_1).create_from_attachment_data(
            attachment_data_list=[{'name': 'sample_contract.pdf', 'datas': self.pdf_data_64}]
        )
        user_1_template_id = res.get('id')
        user_1_template = self.env['sign.template'].with_user(self.user_1).browse(user_1_template_id)
        user_1_document = user_1_template.document_ids[0]
        with self.assertRaises(AccessError):
            user_1_template.with_user(self.user_2).write({'name': 'My New Name!'})
        with self.assertRaises(AccessError):
            user_1_document.with_user(self.user_2).write({'name': 'My New Name!'})

    def test_user_validation_sign_request(self):
        """ Ensure that user cannot link a sign request item with an existing sign request. """
        user_A = new_test_user(self.env, login="user_A", groups='sign.group_sign_user')
        partner_A = user_A.partner_id
        sign_request_A = self.create_sign_request_1_role(partner_A, partner_A)

        user_B = new_test_user(self.env, login="user_B", groups='sign.group_sign_user')
        partner_B = user_B.partner_id
        sign_request_B = self.create_sign_request_1_role(partner_B, partner_B)

        self.assertEqual(self.env['sign.request'].with_user(user_A).search([]), sign_request_A)
        self.assertEqual(self.env['sign.request'].with_user(user_B).search([]), sign_request_B)

        # If we "try to move" a ``sign.request.item`` on an existing ``sign.request`` a validation
        # error must be triggered because we must have the same number of ``sign.request.item`` on the
        # ``sign.request`` and on the ``sign.template`` linked to the ``sign.request``.
        # Thanks to the constraint ``_check_signers_validity``.

        # Test create validation
        with self.assertRaises(ValidationError):
            self.env['sign.request.item'].with_user(user_B).create({
                    'partner_id': partner_B.id,
                    'role_id': self.env.ref('sign.sign_item_role_default').id,
                    'sign_request_id': sign_request_A.id
            })

        # Test write validation
        with self.assertRaises(ValidationError):
            sign_request_B.request_item_ids.with_user(user_B).sign_request_id = sign_request_A
