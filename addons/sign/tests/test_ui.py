# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from .sign_request_common import SignRequestCommon
import odoo.tests

from odoo.tools.misc import file_open


@odoo.tests.tagged('-at_install', 'post_install')
class TestUi(odoo.tests.HttpCase, SignRequestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.user_admin').email = "admin@yourcompany.example.com"

    def test_ui(self):
        # If not enabled (like in demo data), landing on res.config will try
        # to disable module_sale_quotation_builder and raise an issue
        group_order_template = self.env.ref('sale_management.group_sale_order_template', raise_if_not_found=False)
        if group_order_template:
            self.env.ref('base.group_user').write({"implied_ids": [(4, group_order_template.id)]})

        # make sure that we only have the required template.
        self.env['sign.template'].search([('name', '!=', 'template_1_role')]).write({'active': False})

        self.start_tour("/odoo", 'shared_sign_request_tour', login='admin')
        shared_sign_request = self.env['sign.request'].search([('reference', '=', 'template_1_role'), ('state', '=', 'shared')])
        self.assertTrue(shared_sign_request.exists(), 'A shared sign request should be created')
        signed_sign_request = self.env['sign.request'].search([('reference', '=', 'template_1_role'), ('state', '=', 'signed')])
        self.assertTrue(signed_sign_request.exists(), 'A signed sign request should be created')
        self.assertEqual(signed_sign_request.create_uid, self.env.ref('base.user_admin'), 'The signed sign request should be created by the admin')
        signer = self.env['res.partner'].search([('email', '=', 'mitchell.admin@public.com')])
        self.assertTrue(signer.exists(), 'A partner should exists with the email provided while signing')

    def test_translate_sign_instructions(self):
        fr_lang = self.env['res.lang'].with_context(active_test=False).search([('code', '=', 'fr_FR')])
        self.env["base.language.install"].create({
            'overwrite': True,
            'lang_ids': [(6, 0, [fr_lang.id])]
        }).lang_install()
        self.partner_1.lang = 'fr_FR'
        sign_request = self.create_sign_request_1_role(signer=self.partner_1, cc_partners=self.env['res.partner'])
        url = f"/sign/document/{sign_request.id}/{sign_request.request_item_ids.access_token}"
        self.start_tour(url, 'translate_sign_instructions', login=None)

    def test_sign_flow(self):
        self.env['sign.item'].create([{
            'type_id': self.env.ref('sign.sign_item_type_signature').id,
            'required': True,
            'responsible_id': self.role_signer_1.id,
            'page': 1,
            'posX': 0.144,
            'posY': 0.716,
            'document_id': self.document_2.id,
            'width': 0.200,
            'height': 0.050,
        }])
        self.env['sign.template'].search([('id', '!=', self.template_1_role.id)]).write({'active': False})
        self.template_1_role.user_id = self.user_1
        type_id = self.env['sign.item.type'].create({
            'name': "Issuer",
            'item_type': "text",
            'placeholder': "Issued by Laurie Poiret",
        })
        self.env['sign.item'].create([{
            'type_id': type_id.id,
            'required': False,
            'constant': True,
            'responsible_id': self.role_signer_1.id,
            'page': 1,
            'posX': 0.144,
            'posY': 0.716,
            'document_id': self.document_2.id,
            'width': 0.200,
            'height': 0.050,
        }])
        with file_open('sign/static/demo/signature.png', "rb") as f:
            img_content = base64.b64encode(f.read())

        self.user_1.write({
            'sign_signature': img_content,
        })
        self.start_tour("/odoo", 'test_sign_flow_tour', login=self.user_1.login)

    def test_template_edition(self):
        blank_template = self.env['sign.template'].create({
            'name': 'blank_template',
        })

        document = self.env['sign.document'].create({
            'attachment_id': self.attachment.id,
            'template_id': blank_template.id,
        })
        self.start_tour("/odoo", "sign_template_creation_tour", login="admin")
        self.assertEqual(document.name, 'new-document-name', 'The tour should have changed the document name')
        self.assertEqual(len(blank_template.sign_item_ids), 5)
        self.assertEqual(blank_template.responsible_count, 1)
        self.assertEqual(set(blank_template.sign_item_ids.mapped("type_id.item_type")), {"text", "signature"})
        self.assertEqual(set(blank_template.sign_item_ids.mapped("name")), set(["Text", "Name", "Signature"]))

    def test_report_modal(self):
        self.start_tour("/odoo", "sign_report_modal_tour", login="admin")

    def test_sign_tour(self):
        sign_requests = self.env['sign.request'].search([])
        # Step 2 of the `sign_tour` onboarding tour assumes that there's no sign.request record in the database.
        sign_requests.active = False
        self.start_tour("/odoo", "sign_tour", login="admin")

    def test_sign_tour_without_sign(self):
        # The tour has a step for the Signature dialoge, which is relevant only if the user has no saved signature.
        self.env.ref('base.user_admin').sign_signature = False
        sign_requests = self.env['sign.request'].search([])
        # Step 2 of the `sign_tour` onboarding tour assumes that there's no sign.request record in the database.
        sign_requests.active = False
        self.start_tour("/odoo", "sign_tour", login="admin")
