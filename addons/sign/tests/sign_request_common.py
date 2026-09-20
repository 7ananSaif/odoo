# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import Command
from odoo.tools import file_open
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.mail.tests.common import mail_new_test_user
from unittest.mock import patch
from freezegun import freeze_time
from contextlib import contextmanager

class SignRequestCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with file_open('sign/static/demo/sample_contract.pdf', "rb") as f:
            pdf_content = f.read()
            cls.pdf_data_64 = base64.b64encode(pdf_content)

        cls.attachment = cls.env['ir.attachment'].create({
            'type': 'binary',
            'raw': pdf_content,
            'name': 'test_employee_contract.pdf',
        })
        cls.public_user = mail_new_test_user(
            cls.env,
            name='Public user',
            login='public_user',
            email='public_user@example.com',
            groups='base.group_public',
        )

        cls.role_signer_1 = cls.env['sign.item.role'].create({
            'name': 'Signer 1',
            'change_authorized': False,
        })
        cls.role_signer_2 = cls.env['sign.item.role'].create({
            'name': 'Signer 2',
            'change_authorized': False,
        })
        cls.role_signer_3 = cls.env['sign.item.role'].create({
            'name': 'Signer 3',
            'change_authorized': True,
        })

        cls.role_1 = cls.env['sign.item.role'].create({
            'name': 'Customer'
        })

        cls.template_no_item = cls.env['sign.template'].create({
            'name': 'template_no_item',
        })

        cls.template_1_role = cls.env['sign.template'].create({
            'name': 'template_1_role',
        })

        cls.document_1 = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_no_item.id,
        })

        cls.document_2 = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_1_role.id,
        })

        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_1.id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_2.id,
                'width': 0.150,
                'height': 0.015,
            }
        ])
        cls.single_signer_sign_values = cls.create_sign_values(cls, cls.template_1_role.sign_item_ids, cls.role_signer_1.id)

        cls.template_3_roles = cls.env['sign.template'].create({
            'name': 'template_3_roles',
        })
        cls.document_3 = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_3_roles.id,
        })

        cls.template_2_roles = cls.env['sign.template'].create({
            'name': 'template_2_roles',
        })
        cls.document_4 = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_2_roles.id,
        })
        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_1.id,
                'page': 1,
                'posX': 0.373,
                'posY': 0.258,
                'document_id': cls.document_4.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_2.id,
                'page': 1,
                'posX': 0.373,
                'posY': 0.358,
                'document_id': cls.document_4.id,
                'width': 0.150,
                'height': 0.015,
            },
        ])

        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_1.id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_3.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_2.id,
                'page': 1,
                'posX': 0.373,
                'posY': 0.258,
                'document_id': cls.document_3.id,
                'width': 0.150,
                'height': 0.015,
            }, {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.role_signer_3.id,
                'page': 1,
                'posX': 0.373,
                'posY': 0.358,
                'document_id': cls.document_3.id,
                'width': 0.150,
                'height': 0.015,
            },
        ])

        cls.template_constant = cls.env['sign.template'].create({
            'name': 'template_constant',
        })

        cls.document_constant = cls.env['sign.document'].create({
            'attachment_id': cls.attachment.id,
            'template_id': cls.template_constant.id
        })

        cls.env['sign.item'].create({
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': False,
                'constant': True,
                'responsible_id': cls.role_1.id,
                'page': 1,
                'posX': 0.273,
                'posY': 0.158,
                'document_id': cls.document_constant.id,
                'width': 0.150,
                'height': 0.015,
        })

        cls.signature_fake = base64.b64encode(b"fake_signature")
        cls.signer_1_sign_values = cls.create_sign_values(cls, cls.template_3_roles.sign_item_ids, cls.role_signer_1.id)
        cls.signer_2_sign_values = cls.create_sign_values(cls, cls.template_3_roles.sign_item_ids, cls.role_signer_2.id)
        cls.signer_3_sign_values = cls.create_sign_values(cls, cls.template_3_roles.sign_item_ids, cls.role_signer_3.id)

        cls.signer_1_sign_values_2_roles = cls.create_sign_values(cls, cls.template_2_roles.sign_item_ids, cls.role_signer_1.id)
        cls.signer_2_sign_values_2_roles = cls.create_sign_values(cls, cls.template_2_roles.sign_item_ids, cls.role_signer_2.id)

        cls.user_1 = new_test_user(cls.env, login="user_1", groups='sign.group_sign_user')
        cls.partner_1 = cls.user_1.partner_id
        cls.partner_1.write({
            'name': 'Laurie Poiret',
            'street': '57 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543210',
            'email': 'laurie.poiret.a@example.com',
        })

        cls.user_2 = new_test_user(cls.env, login="user_2", password='user_2!user_2', groups='sign.group_sign_user')
        cls.partner_2 = cls.user_2.partner_id
        cls.partner_2.write({
            'name': 'Bernardo Ganador',
            'street': '58 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543209',
            'email': 'bernardo.ganador.a@example.com',
        })

        cls.user_3 = new_test_user(cls.env, login="user_3", groups='sign.group_sign_user')
        cls.partner_3 = cls.user_3.partner_id
        cls.partner_3.write({
            'name': 'Martine Poulichette',
            'street': '59 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543211',
            'email': 'martine.poulichette.a@example.com',
        })

        cls.user_4 = new_test_user(cls.env, login="user_4", groups='sign.group_sign_user')
        cls.partner_4 = cls.user_4.partner_id
        cls.partner_4.write({
            'name': 'Ignasse Reblochon',
            'street': '60 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543212',
            'email': 'ignasse.reblochon.a@example.com',
        })

        cls.user_5 = new_test_user(cls.env, login="user_5", groups='base.group_user')
        cls.partner_5 = cls.user_5.partner_id
        cls.partner_5.write({
            'name': 'Char Aznable',
            'street': '61 rue des Wallons',
            'city': 'Louvain-la-Neuve',
            'zip': '1348',
            'country_id': cls.env.ref("base.be").id,
            'phone': '+0032476543213',
            'email': 'char.aznable.a@example.com',
        })

    @contextmanager
    def mock_datetime_and_now(self, mock_dt):
        with freeze_time(mock_dt), \
                patch.object(self.env.cr, 'now', lambda: mock_dt):
            yield

    def create_sign_request_no_item(self, signer, cc_partners, no_sign_mail=False, validity=False):
        sign_request = self.env['sign.request'].with_context(no_sign_mail=no_sign_mail).create({
            'template_id': self.template_no_item.id,
            'reference': self.template_no_item.display_name,
            'request_item_ids': [Command.create({
                'partner_id': signer.id,
                'role_id': self.env.ref('sign.sign_item_role_default').id,
            })],
            'validity': validity,
        })
        sign_request.message_subscribe(partner_ids=cc_partners.ids)
        return sign_request

    def create_sign_request_1_role(self, signer, cc_partners):
        sign_request = self.env['sign.request'].create({
            'template_id': self.template_1_role.id,
            'reference': self.template_1_role.display_name,
            'request_item_ids': [Command.create({
                'partner_id': signer.id,
                'role_id': self.role_signer_1.id,
            })],
        })
        sign_request.message_subscribe(partner_ids=cc_partners.ids)
        return sign_request

    def create_sign_request_1_role_sms_auth(self, signer, cc_partners):
        self.role_signer_1.auth_method = 'sms'
        return self.create_sign_request_1_role(signer, cc_partners)

    def create_sign_request_2_roles(self, signer_1, signer_2, cc_partners):
        sign_request = self.env['sign.request'].create({
            'template_id': self.template_2_roles.id,
            'reference': self.template_2_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': signer_1.id,
                'role_id': self.role_signer_1.id,
            }), Command.create({
                'partner_id': signer_2.id,
                'role_id': self.role_signer_2.id,
            })],
        })
        sign_request.message_subscribe(partner_ids=cc_partners.ids)
        return sign_request

    def create_sign_request_3_roles(self, signer_1, signer_2, signer_3, cc_partners):
        sign_request = self.env['sign.request'].create({
            'template_id': self.template_3_roles.id,
            'reference': self.template_3_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': signer_1.id,
                'role_id': self.role_signer_1.id,
            }), Command.create({
                'partner_id': signer_2.id,
                'role_id': self.role_signer_2.id,
            }), Command.create({
                'partner_id': signer_3.id,
                'role_id': self.role_signer_3.id,
            })],
        })
        sign_request.message_subscribe(partner_ids=cc_partners.ids)
        return sign_request

    def create_sign_request_with_constant_field(self, customer, cc_partners):
        sign_request = self.env['sign.request'].create({
            'template_id': self.template_constant.id,
            'reference': self.template_constant.display_name,
            'request_item_ids': [Command.create({
                'partner_id': customer.id,
                'role_id': self.role_1.id
            })],
        })
        sign_request.message_subscribe(partner_ids=cc_partners.ids)
        return sign_request

    def get_sign_item_config(self, role_id):
        return {
                'type_id': self.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'option_ids': [],
                'responsible_id': role_id,
                'page': 1,
                'posX': 0.1,
                'posY': 0.2,
                'width': 0.15,
                'height': 0.15,
                'document_id': self.document_3.id,
        }

    def create_sign_values(self, sign_item_ids, role_id):
        return {
            str(sign_id): 'a'
            for sign_id in sign_item_ids
            .filtered(lambda r: not r.responsible_id or r.responsible_id.id == role_id)
            .ids
        }
