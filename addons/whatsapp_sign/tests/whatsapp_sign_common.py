# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, new_test_user


class WhatsAppSignCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sign_request_wa_template = cls.env['whatsapp.template'].create({
            "model_id": cls.env['ir.model']._get_id('sign.request.item'),
            "phone_field": "partner_id.phone",
            'body': 'receiver name: {{1}},\n\n'
                    'sender name: {{2}}\n\n'
                    'document name: {{3}}\n\n'
                    'signature link: {{4}}\n\n'
                    'additional details: {{5}}\n\n'
                    'expiration: {{6}}\n\n'
                    'attachments: {{7}}',
            'name': 'Demo Sign Request Template',
            'status': 'approved',
            'variable_ids': [
                (5, 0, 0),
                (0, 0, {
                    'name': '{{1}}', 'demo_value': 'Mark', 'line_type': 'body', 'field_type': 'field', 'field_name': 'display_name'
                }),
                (0, 0, {
                    'name': '{{2}}', 'demo_value': 'Mitchell', 'line_type': 'body', 'field_type': 'field', 'field_name': 'create_uid.partner_id.name'
                }),
                (0, 0, {
                    'name': '{{3}}', 'demo_value': 'Doc.pdf', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.reference'
                }),
                (0, 0, {
                    'name': '{{4}}', 'demo_value': 'https://...', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_link'
                }),
                (0, 0, {
                    'name': '{{5}}', 'demo_value': 'Optional message', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.raw_optional_message'
                }),
                (0, 0, {
                    'name': '{{6}}', 'demo_value': '2025-10-14', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.validity'
                }),
                (0, 0, {
                    'name': '{{7}}', 'demo_value': 'https://...', 'line_type': 'body', 'field_type': 'field', 'field_name': 'attachments_download_link'
                })
            ],
        })
        cls.env['ir.config_parameter'].sudo().set_param('whatsapp_sign.whatsapp_template_id',
                                                        cls.sign_request_wa_template.id)

        cls.sign_completion_wa_template = cls.env['whatsapp.template'].create({
            "model_id": cls.env['ir.model']._get_id('sign.request.item'),
            "phone_field": "partner_id.phone",
            'body': 'receiver name: {{1}}\n\n'
                    'document name: {{2}}\n\n'
                    'signer name: {{3}}\n\n'
                    'document link: {{4}}\n\n',
            'name': 'Demo Sign Completion Template',
            'status': 'approved',
            'variable_ids': [
                (5, 0, 0),
                (0, 0, {
                    'name': '{{1}}', 'demo_value': 'Mark', 'line_type': 'body', 'field_type': 'field', 'field_name': 'display_name'
                }),
                (0, 0, {
                    'name': '{{2}}', 'demo_value': 'Doc.pdf', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.reference'
                }),
                (0, 0, {
                    'name': '{{3}}', 'demo_value': 'Moustafa and you', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.signers_name'
                }),
                (0, 0, {
                    'name': '{{4}}', 'demo_value': 'https://...', 'line_type': 'body', 'field_type': 'field', 'field_name': 'document_link'
                })
            ],
        })
        cls.env['ir.config_parameter'].sudo().set_param('whatsapp_sign.whatsapp_completion_template_id',
                                                        cls.sign_completion_wa_template.id)

        cls.sign_refusal_wa_template = cls.env['whatsapp.template'].create({
            "model_id": cls.env['ir.model']._get_id('sign.request.item'),
            "phone_field": "partner_id.phone",
            'body': 'receiver name: {{1}}\n\n'
                    'refuser name: {{2}}\n\n'
                    'document name: {{3}}\n\n'
                    'refusal reason: {{4}}\n\n'
                    'document link: {{5}}\n\n',
            'name': 'Demo Sign Completion Template',
            'status': 'approved',
            'variable_ids': [
                (5, 0, 0),
                (0, 0, {
                    'name': '{{1}}', 'demo_value': 'Mark', 'line_type': 'body', 'field_type': 'field', 'field_name': 'display_name'
                }),
                (0, 0, {
                    'name': '{{2}}', 'demo_value': 'Moustafa', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.refuser_partner.name'
                }),
                (0, 0, {
                    'name': '{{3}}', 'demo_value': 'Doc.pdf', 'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.reference'
                }),
                (0, 0, {
                    'name': '{{4}}', 'demo_value': 'I’m unable to sign at this time due to unresolved concerns.',
                    'line_type': 'body', 'field_type': 'field', 'field_name': 'sign_request_id.refusal_reason'
                }),
                (0, 0, {
                    'name': '{{5}}', 'demo_value': 'https://...', 'line_type': 'body', 'field_type': 'field', 'field_name': 'document_link'
                })
            ],
        })
        cls.env['ir.config_parameter'].sudo().set_param('whatsapp_sign.whatsapp_refusal_template_id',
                                                        cls.sign_refusal_wa_template.id)

        cls.whatsapp_template_ids = [
            cls.sign_request_wa_template.id,
            cls.sign_completion_wa_template.id,
            cls.sign_refusal_wa_template.id
        ]

        cls.test_sign_user = new_test_user(
            cls.env,
            login="test_sign_user",
            groups='sign.group_sign_user'
        )
        cls.partner_without_phone = cls.test_sign_user.partner_id
        cls.partner_without_phone.write({
            'name': 'Leo Dubois',
            'street': '42 Rue de la Liberté',
            'city': 'Lyon',
            'zip': '69003',
            'country_id': cls.env.ref("base.fr").id,
            'email': 'leo.dubois@example.com',
        })

    def search_for_wa_messages(self, wa_template_id):
        return self.env['whatsapp.message'].search([
            ('wa_template_id', '=', wa_template_id)
        ])

    def create_sign_send_request_wizard(self, template, partner_ids):
        wizard = self.env['sign.send.request'].with_context(active_id=template.id).create({
            'subject': f'Sign Request - {template.name}',
            'template_id': template.id,
        })

        roles = template.sign_item_ids.responsible_id.sorted()
        wizard.signers_count = len(roles)

        signer_commands = [(5, 0, 0)]
        for idx, (role, partner_ids) in enumerate(zip(roles, partner_ids), start=1):
            signer_commands.append((0, 0, {
                'role_id': role.id,
                'partner_id': partner_ids,
                'mail_sent_order': idx,
            }))

        wizard.write({'signer_ids': signer_commands})

        return wizard

    def get_sign_request_items(self, template_id):
        sign_request = self.env['sign.request'].search([('template_id', '=', template_id)])
        sign_items = sign_request.request_item_ids.sorted(key=lambda sri: sri.mail_sent_order)

        return sign_items

    def get_whatsapp_templates(self):
        wa_templates = []
        for template_id in self.whatsapp_template_ids:
            wa_templates.append(self.env['whatsapp.template'].browse(int(template_id)))

        return wa_templates
