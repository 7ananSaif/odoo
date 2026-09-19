# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, users
from odoo.tools import formataddr

from odoo.addons.mail.tests.common import MockEmail
from .sign_request_common import SignRequestCommon, freeze_time

from datetime import timedelta


class TestSignRequest(SignRequestCommon, MockEmail):
    def test_sign_request_create(self):
        sign_request_no_item = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)

        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)

        for sign_request in [sign_request_no_item, sign_request_3_roles]:
            self.assertTrue(sign_request.exists(), 'A sign request with no sign item should be created')
            self.assertEqual(sign_request.state, 'sent', 'The default state for a new created sign request should be "sent"')
            self.assertTrue(all(sign_request.request_item_ids.mapped('is_mail_sent')), 'The mail should be sent for the new created sign request by default')
            self.assertEqual(sign_request.with_context(active_test=False).cc_partner_ids, self.partner_4, 'The cc_partners should be the specified one and the creator unless the creator is inactive')
            self.assertEqual(len(sign_request.sign_log_ids.filtered(lambda log: log.action == 'create')), 1, 'A log with action="create" should be created')
            for sign_request_item in sign_request:
                self.assertEqual(sign_request_item.state, 'sent', 'The default state for a new created sign request item should be "sent"')
        self.assertEqual(len(sign_request_no_item.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'An activity should be scheduled for signers with Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_5.id)), 0, 'An activity should not be scheduled for signers without Sign Access')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_4.id)), 0, 'An activity should not be scheduled for CC partners')

        SignRequest = self.env['sign.request']
        with self.assertRaises(ValidationError, msg='A sign request with no sign item needs a signer'):
            SignRequest.create({
                'template_id': self.template_no_item.id,
                'reference': self.template_no_item.display_name,
            })

        with self.assertRaises(ValidationError, msg='A sign request with no sign item can only have the default role'):
            SignRequest.create({
                'template_id': self.template_no_item.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_3.id,
                })],
                'reference': self.template_no_item.display_name,
            })

        with self.assertRaises(ValidationError, msg='Three roles need three singers'):
            SignRequest.create({
                'template_id': self.template_3_roles.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                }), Command.create({
                    'partner_id': self.partner_2.id,
                    'role_id': self.role_signer_2.id,
                })],
                'reference': self.template_3_roles.display_name,
            })

        with self.assertRaises(ValidationError, msg='A role cannot be shared with two signers'):
            SignRequest.create({
                'template_id': self.template_3_roles.id,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                }), Command.create({
                    'partner_id': self.partner_2.id,
                    'role_id': self.role_signer_2.id,
                }), Command.create({
                    'partner_id': self.partner_3.id,
                    'role_id': self.role_signer_3.id,
                }), Command.create({
                    'partner_id': self.partner_4.id,
                    'role_id': self.role_signer_3.id,
                })],
                'reference': self.template_3_roles.display_name,
            })

    def test_sign_request_no_item_create_sign_cancel_copy(self):
        # create
        sign_request_no_item = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        sign_request_item = sign_request_no_item.request_item_ids[0]

        # sign
        with self.assertRaises(UserError, msg='A sign.request.item can only sign its sign.items'):
            sign_request_item.sign(self.signer_1_sign_values)
        sign_request_item.sign(self.signature_fake)
        self.assertEqual(sign_request_item.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_no_item.state, 'signed', 'The sign request should be signed')
        self.assertEqual(len(sign_request_no_item.completed_document_attachment_ids), 2, 'The completed document and the certificate should be created')
        self.assertEqual(len(sign_request_no_item.sign_log_ids.filtered(
            lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item)),
            1, 'A log with action="sign" should be created')
        self.assertEqual(len(sign_request_no_item.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity should be removed after signing')
        with self.assertRaises(UserError, msg='A document cannot be signed twice'):
            sign_request_item.sign(self.signature_fake)

        # unlink
        with self.assertRaises(UserError, msg='A signed sign request cannot be unlinked'):
            sign_request_no_item.unlink()

        # cancel
        sign_request_item_token = sign_request_item.access_token
        sign_request_no_item_token = sign_request_no_item.access_token
        sign_request_no_item.cancel()
        self.assertEqual(sign_request_item.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_no_item.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item.access_token, sign_request_item_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_no_item.access_token, sign_request_no_item_token, 'The access token should be changed')
        self.assertEqual(len(sign_request_no_item.sign_log_ids.filtered(lambda log: log.action == 'cancel')), 1, 'A log with action="cancel" should be created')

        # copy
        new_sign_request_no_item = sign_request_no_item.copy()
        self.assertTrue(new_sign_request_no_item.exists(), 'A sign request with no sign item should be created')
        self.assertEqual(new_sign_request_no_item.state, 'sent', 'The default state for a new created sign request should be "sent"')
        self.assertTrue(all(new_sign_request_no_item.request_item_ids.mapped('is_mail_sent')), 'The mail should be sent for the new created sign request by default')
        self.assertEqual(new_sign_request_no_item.with_context(active_test=False).cc_partner_ids, self.partner_4, 'The cc_partners should be the specified one and the creator unless he is inactive')
        self.assertEqual(len(new_sign_request_no_item.sign_log_ids.filtered(lambda log: log.action == 'create')), 1, 'A log with action="create" should be created')
        for sign_request_item in new_sign_request_no_item:
            self.assertEqual(sign_request_item.state, 'sent', 'The default state for a new created sign request item should be "sent"')
        self.assertNotEqual(new_sign_request_no_item.access_token, sign_request_no_item.access_token, 'The access_token should be changed')
        self.assertNotEqual(new_sign_request_no_item.request_item_ids[0].access_token, sign_request_no_item.request_item_ids[0].access_token, 'The access_token should be changed')

    def test_sign_request_3_roles_create_sign_cancel(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # sign
        with self.assertRaises(UserError, msg='A sign.request.item can only sign its sign.items'):
            sign_request_item_signer_2.sign(self.signer_1_sign_values)
        sign_request_item_signer_1.sign(self.signer_1_sign_values)
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'sent', 'The sign.request.item should be sent')
        self.assertEqual(sign_request_item_signer_3.state, 'sent', 'The sign.request.item should be sent')
        self.assertEqual(sign_request_3_roles.state, 'sent', 'The sign request should be signed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(
            lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item_signer_1)),
            1, 'A log with action="sign" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity should be removed after signing')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'The activity should not be removed for unsigned signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 1, 'The activity should not be removed for unsigned signer')
        with self.assertRaises(UserError, msg='A document cannot be signed twice'):
            sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # cancel
        sign_request_item_signer_1_token = sign_request_item_signer_1.access_token
        sign_request_item_signer_2_token = sign_request_item_signer_2.access_token
        sign_request_item_signer_3_token = sign_request_item_signer_3.access_token
        sign_request_3_roles_token = sign_request_3_roles.access_token
        sign_request_3_roles.cancel()
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(lambda log: log.action == 'cancel')), 1, 'A log with action="cancel" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity should be removed after cancellation')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'The activity should be removed after cancellation')

    def test_sign_request_3_roles_create_sign_refuse_cancel(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # sign (test has been done in test_sign_request_3_roles_create_sign_cancel)
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # refuse
        with self.assertRaises(UserError, msg='A signed sign.request.item cannot be refused'):
            sign_request_item_signer_1._refuse(request_state='sent', refusal_reason="bad document")
        sign_request_item_signer_1_token = sign_request_item_signer_1.access_token
        sign_request_item_signer_2_token = sign_request_item_signer_2.access_token
        sign_request_item_signer_3_token = sign_request_item_signer_3.access_token
        sign_request_3_roles_token = sign_request_3_roles.access_token
        sign_request_item_signer_2._refuse(request_state='sent', refusal_reason='bad document')
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(
            lambda log: log.action == 'refuse' and log.sign_request_item_id == sign_request_item_signer_2)),
            1, 'A log with action="refuse" should be created')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity should be removed for refused signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'The activity should be removed for remaining signers')

        with self.assertRaises(UserError, msg='A canceled sign.request.item cannot be signed'):
            sign_request_item_signer_3.sign(self.signer_3_sign_values)

        # cancel
        sign_request_3_roles.cancel()
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'canceled', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'canceled', 'The sign.request.item should be canceled')
        self.assertEqual(sign_request_3_roles.state, 'canceled', 'The sign request should be canceled')
        self.assertNotEqual(sign_request_item_signer_1.access_token, sign_request_item_signer_1_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_2.access_token, sign_request_item_signer_2_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_item_signer_3.access_token, sign_request_item_signer_3_token, 'The access token should be changed')
        self.assertNotEqual(sign_request_3_roles.access_token, sign_request_3_roles_token, 'The access token should be changed')
        # now the cancel method is also called from refuse method so the log count is become 2
        self.assertEqual(len(sign_request_3_roles.sign_log_ids.filtered(lambda log: log.action == 'cancel')), 2, 'A log with action="cancel" should be created')

    def test_sign_request_refuse_shared(self):
        """ Ensure that shared sign requests can be refused by public users. """
        # Get the shared request from a template with one role.
        wizard_id = self.template_1_role.open_shared_sign_request()['res_id']
        wizard = self.env['sign.request.share'].browse(wizard_id)
        shared_request = wizard.sign_request_id
        sign_request_item = shared_request.request_item_ids[0]

        with self.assertRaises(UserError):
            # Ensure an user error is raised by not specifying the refusal email.
            sign_request_item.with_user(self.public_user).sudo()._refuse(
                request_state="shared",
                refusal_reason="Reason",
                refusal_name="Marc"
            )

        sign_request_item.with_user(self.public_user).sudo()._refuse(
            request_state="shared",
            refusal_reason="Reason",
            refusal_name="Marc",
            refusal_email="demo@odoo.com"
        )
        self.assertEqual(shared_request.state, "shared", "Previous request must remain shared.")

        refused_public_user = self.env['res.partner'].search([('email', '=', 'demo@odoo.com')])
        self.assertTrue(refused_public_user, "Ensure that the partner from the public user was created.")

        refused_request_item = self.env['sign.request.item'].search([('partner_id', '=', refused_public_user.id)])
        self.assertEqual(len(refused_request_item), 1, "Ensure that the refused request item was created.")

        refused_request = self.env['sign.request'].search([
            ('state', '=', 'canceled'),
            ('id', '>', shared_request.id)
        ])
        self.assertEqual(len(refused_request), 1, "Ensure that the refused request was created.")

    def test_sign_request_item_auto_resend(self):
        # create
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        request_item_ids = sign_request.request_item_ids
        request_item = request_item_ids[0]
        token_a = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertEqual(request_item.is_mail_sent, True, 'email should be sent')

        # resend the document
        request_item.send_signature_accesses()
        self.assertEqual(request_item.access_token, token_a, "sign request item's access token should not be changed")

        # change the email address of the signer (laurie.poiret.b)
        with self.assertRaises(ValidationError, msg='All signers must have valid email addresses'):
            self.partner_1.write({'email': 'laurie.poiret.b'})

        # change the email address to upper case (LAURIE.POIRET.A@example.com)
        self.partner_1.write({'email': 'LAURIE.POIRET.A@example.com'})
        self.assertEqual(request_item.signer_email, "laurie.poiret.a@example.com", 'email address should not be changed as is the same email')
        self.assertFalse(
            sign_request.sign_log_ids.filtered(lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item),
            'No log with action="update_mail" should be created after changing the email to upper case'
        )

        # change the email address of the signer (laurie.poiret.b@example.com)
        self.partner_1.write({'email': 'laurie.poiret.b@example.com'})
        token_b = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')
        self.assertNotEqual(token_b, token_a, "sign request item's access token should be changed")
        self.assertEqual(len(sign_request.sign_log_ids.filtered(
            lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item)),
            1, 'A log with action="update_mail" should be created')
        self.assertEqual(len(sign_request.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'The number of activities should still be 1')

        # sign the document
        request_item.sign(self.signature_fake)
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')

        # change the email address of the signer (laurie.poiret.c@example.com)
        self.partner_1.write({'email': 'laurie.poiret.c@example.com'})
        token_c = request_item.access_token
        self.assertEqual(request_item.signer_email, "laurie.poiret.b@example.com", 'email address should be laurie.poiret.b@example.com')
        self.assertEqual(token_c, token_b, "sign request item's access token should be not changed after the document is signed by the signer")
        self.assertEqual(len(sign_request.sign_log_ids.filtered(
            lambda log: log.action == 'update_mail' and log.sign_request_item_id == request_item)),
            1, 'No new log with action="update_mail" should be created')

    def test_sign_request_item_reassign_sign_reassign_refuse_reassign(self):
        # create
        sign_request_3_roles = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2,
                                                                signer_3=self.partner_3, cc_partners=self.partner_4)
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]

        # reassign
        self.assertEqual(sign_request_item_signer_1.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertEqual(sign_request_item_signer_1.is_mail_sent, True, 'email should be sent')
        token_signer_1 = sign_request_item_signer_1.access_token
        with self.assertRaises(UserError, msg='Reassigning a role without change_authorized is not allowed'):
            sign_request_item_signer_1.write({'partner_id': self.partner_5.id})
        sign_request_item_signer_1.role_id.change_authorized = True
        with self.assertRaises(UserError, msg='Reassigning the partner_id to False is not allowed'):
            sign_request_item_signer_1.write({'partner_id': False})
        logs_num = len(sign_request_3_roles.sign_log_ids)
        sign_request_item_signer_1.write({'partner_id': self.partner_5.id})
        self.assertEqual(sign_request_item_signer_1.signer_email, "char.aznable.a@example.com", 'email address should be char.aznable.a@example.com')
        self.assertNotEqual(sign_request_item_signer_1.access_token, token_signer_1, "sign request item's access token should be changed")
        self.assertEqual(sign_request_item_signer_1.is_mail_sent, False, 'email should not be sent')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids), logs_num, 'No new log should be created')
        self.assertEqual(sign_request_3_roles.with_context(active_test=False).cc_partner_ids, self.partner_4 + self.partner_1, 'If a signer is reassigned and no longer be a signer, he should be a contact in copy')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 0, 'The activity for the old signer should be removed')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_5.id)), 0, 'No activity should be created for user without permission to access Sign')

        # sign
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # reassign
        token_signer_2 = sign_request_item_signer_1.access_token
        with self.assertRaises(UserError, msg='A signed sign request item cannot be reassigned'):
            sign_request_item_signer_1.write({'partner_id': self.partner_1.id})
        sign_request_item_signer_2.role_id.change_authorized = True
        logs_num = len(sign_request_3_roles.sign_log_ids)
        sign_request_item_signer_2.write({'partner_id': self.partner_1.id})
        self.assertEqual(sign_request_item_signer_2.signer_email, "laurie.poiret.a@example.com", 'email address should be laurie.poiret.a@example.com')
        self.assertNotEqual(sign_request_item_signer_2.access_token, token_signer_2, "sign request item's access token should be changed")
        self.assertEqual(sign_request_item_signer_2.is_mail_sent, False, 'email should not be sent')
        self.assertEqual(len(sign_request_3_roles.sign_log_ids), logs_num, 'No new log should be created')
        self.assertEqual(sign_request_3_roles.with_context(active_test=False).cc_partner_ids, self.partner_4 + self.partner_2, 'If a signer is reassigned and no longer be a signer, he should be a contact in copy')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'The activity for the old signer should be removed')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity for the new signer should be created')

        # refuse
        sign_request_item_signer_2._refuse(request_state='sent', refusal_reason='bad request')

        # reassign
        with self.assertRaises(UserError, msg='A refused sign request item cannot be reassigned'):
            sign_request_item_signer_2.write({'partner_id': self.partner_2.id})
        with self.assertRaises(UserError, msg='A canceled sign request item cannot be reassigned'):
            sign_request_item_signer_3.write({'partner_id': self.partner_2.id})

    def test_sign_request_mail_sent_order(self):
        sign_request_3_roles = self.env['sign.request'].create({
            'template_id': self.template_3_roles.id,
            'reference': self.template_3_roles.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.role_signer_1.id,
                'mail_sent_order': 1,
            }), Command.create({
                'partner_id': self.partner_2.id,
                'role_id': self.role_signer_2.id,
                'mail_sent_order': 2,
            }), Command.create({
                'partner_id': self.partner_3.id,
                'role_id': self.role_signer_3.id,
                'mail_sent_order': 2,
            })],
        })
        role2sign_request_item = dict([(sign_request_item.role_id, sign_request_item) for sign_request_item in sign_request_3_roles.request_item_ids])
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_1.id)), 1, 'An activity should be scheduled for the first signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 0, 'No activity should be scheduled for the second signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 0, 'No activity should be scheduled for the third signer')
        self.assertTrue(sign_request_item_signer_1.is_mail_sent, 'An email should be sent for the first signer')
        self.assertFalse(sign_request_item_signer_2.is_mail_sent, 'No email should be sent for the second signer')
        self.assertFalse(sign_request_item_signer_3.is_mail_sent, 'No email should be sent for the third signer')

        # sign
        sign_request_item_signer_1.sign(self.signer_1_sign_values)
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_2.id)), 1, 'An activity should be scheduled for the second signer')
        self.assertEqual(len(sign_request_3_roles.activity_search(['sign.mail_activity_data_signature_request'], user_id=self.user_3.id)), 1, 'An activity should be scheduled for the third signer')
        self.assertTrue(sign_request_item_signer_2.is_mail_sent, 'An email should be sent for the second signer')
        self.assertTrue(sign_request_item_signer_3.is_mail_sent, 'An email should be sent for the third signer')

        # sign and sign
        sign_request_item_signer_2.sign(self.signer_2_sign_values)
        sign_request_item_signer_3.sign(self.signer_3_sign_values)
        self.assertEqual(sign_request_3_roles.state, 'signed', 'The sign request should be signed')

    def test_sign_request_mail_reply_to_exists(self):
        sign_request = self.create_sign_request_1_role(self.partner_1, self.env['res.partner'])
        responsible_email = sign_request.create_uid.email_formatted
        mail = sign_request._message_send_mail(
            "body",
            record_name=sign_request.reference,
            notif_values={
                'model_description': 'signature',
                'company': self.env.company,
                'partner': sign_request.request_item_ids[0].partner_id,
            },
            mail_values={
                'attachment_ids': [],
                'subject': sign_request.subject
            },
        )

        self.assertEqual(mail.reply_to, responsible_email, 'reply_to is not set as the responsible email')

    def test_sign_send_request_without_order(self):
        wizard = Form(self.env['sign.send.request'].with_context(default_template_id=self.template_3_roles.id, sign_directly_without_mail=False))
        self.assertEqual([record['mail_sent_order'] for record in wizard.signer_ids._records], [1, 1, 1])

    def test_sign_send_request_order_with_order(self):
        wizard = Form(self.env['sign.send.request'].with_context(default_template_id=self.template_3_roles.id, sign_directly_without_mail=False))
        wizard.set_sign_order = True
        self.assertEqual([record['mail_sent_order'] for record in wizard.signer_ids._records], [1, 2, 3])

    def test_archived_requests_dont_send_reminders(self):
        """ Create a request with a validity period and archive it, jump to the future
        where it's not valid anymore, trigger cron reminder and ensure no reminder was created. """

        with self.mock_datetime_and_now("2024-05-01"):
            validity_date = fields.Date.from_string('2024-05-05')
            archived_request = self.create_sign_request_no_item(
                signer=self.partner_1,
                cc_partners=self.partner_4,
                validity=validity_date
            )
            # This action should set the state to canceled.
            archived_request.action_archive()

            # Jump to the future and run the cron
            with self.mock_datetime_and_now("2024-05-06"):
                self.env['sign.request']._cron_reminder()
                self.assertTrue(archived_request.state == 'canceled')

    def test_send_request_with_default_sign_template(self):
        sign_request_record = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4)
        activity_type = self.env['mail.activity.type'].create({
            'name': 'Signature',
            'category': 'sign_request',
        })
        activity = self.env['mail.activity'].create({
            'activity_type_id': activity_type.id,
            'res_model_id': self.env['ir.model']._get('sign.request').id,
            'res_id': sign_request_record.id,
        })

        # No default template is set for activity type
        action = self.env['sign.template'].with_context(default_activity_id=activity.id).open_sign_send_dialog()
        wizard = self.env['sign.send.request'].with_context(action['context']).new()
        self.assertFalse(wizard.template_id)

        # Default template is set for activity type
        activity_type.write({'default_sign_template_id': self.template_1_role.id})

        # Login user is not set as responsible(Template is not accessible)
        env = self.env(user=self.user_1)
        action = env['sign.template'].with_context(default_activity_id=activity.id).open_sign_send_dialog()
        wizard = self.env['sign.send.request'].with_context(action['context']).new()
        self.assertFalse(wizard.template_id)

        # Login user is set as responsible(Template is accessible)
        self.template_1_role.write({'user_id': self.user_1.id})
        action = self.env['sign.template'].with_context(default_activity_id=activity.id, arj=True).open_sign_send_dialog()
        wizard = self.env['sign.send.request'].with_context(action['context']).new()
        self.assertEqual(self.template_1_role, wizard.template_id)

    @users('admin')
    def test_sign_request_notification(self):
        """
        Test the sign request notification by creating a user with notification settings
        and checking if the notification type is set to 'inbox' in the created sign request.
        """
        self.env.user.write({
            'name': 'Mitchell Admin',
            'email': 'admin@example.com',
            'notification_type': 'inbox',
        })

        with self.mock_mail_gateway():
            # Create a sign request
            sign_request = self.env['sign.request'].create({
                'template_id': self.template_1_role.id,
                'reference': self.template_1_role.display_name,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.role_signer_1.id,
                    'mail_sent_order': 1,
                })],
                'subject': 'Test Sign Request',
                'message': 'Please sign this document',
            })

            # Map the sign request items by role
            sign_request_items_by_role = {item.role_id: item for item in sign_request.request_item_ids}
            sign_request_item_signer_1 = sign_request_items_by_role[self.role_signer_1]

            # Ensure the sign request is created with the correct state
            self.assertEqual(sign_request.state, 'sent', 'The sign request should be in "sent" state initially')

            # Verify that an email was sent to the signer
            mail = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.partner_1.name, self.partner_1.email)))
            ], limit=1)

            self.assertTrue(mail, 'The initial sign request email should have been sent to the signer_1')
            self.assertSentEmail('"Mitchell Admin" <admin@example.com>', self.partner_1)
            self.assertTrue(sign_request_item_signer_1.is_mail_sent, 'An email should be marked as sent for the signer_1')

            # Simulate signing the document
            sign_request_item_signer_1.sudo().sign(self.single_signer_sign_values)
            self.assertEqual(sign_request.state, 'signed', 'The sign request should be signed')

            completion_mail_to_user = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.env.user.partner_id.name, self.env.user.partner_id.email)))
            ])
            self.assertEqual(0, len(completion_mail_to_user), 'No completion email should be sent to the admin user')

            completion_mail_to_partner = self.env['mail.mail'].search([
                ('email_to', '=', formataddr((self.partner_1.name, self.partner_1.email)))
            ])
            self.assertEqual(
                2, len(completion_mail_to_partner),
                'Two emails should have been sent to the partner: the initial sign request and the completion email'
            )

    def test_check_state_for_download(self):
        """Test downloading a completed document for signed requests and validation for unsigned requests."""

        # Create sign request with 3 roles (signer_1, signer_2, signer_3, cc partners)
        sign_request_3_roles = self.create_sign_request_3_roles(
            signer_1=self.partner_1,
            signer_2=self.partner_2,
            signer_3=self.partner_3,
            cc_partners=self.partner_4
        )
        # Map role to corresponding sign request item using a dictionary comprehension
        role2sign_request_item = {
            sign_request_item.role_id: sign_request_item
            for sign_request_item in sign_request_3_roles.request_item_ids
        }
        # Retrieve individual sign request items for signer 1, 2, and 3
        sign_request_item_signer_1 = role2sign_request_item[self.role_signer_1]
        sign_request_item_signer_2 = role2sign_request_item[self.role_signer_2]
        sign_request_item_signer_3 = role2sign_request_item[self.role_signer_3]
        # Get template and sign item IDs
        template = sign_request_3_roles.template_id
        sign_item_ids = template.sign_item_ids.ids
        # Sign the customer sign request item
        sign_request_item_signer_1.sign(self.signer_1_sign_values)

        # Assertions after signing the signer_1 sign request item
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_3_roles.state, 'sent', 'The sign request should be signed')
        self.assertEqual(template.sign_item_ids.ids, sign_item_ids, 'The original template should not be changed')
        self.assertEqual(
            len(sign_request_3_roles.sign_log_ids.filtered(
                lambda log: log.action == 'sign' and log.sign_request_item_id == sign_request_item_signer_1
            )),
            1, 'A log with action="sign" should be created'
        )
        # Sign the employee sign request item
        sign_request_item_signer_2.sign(
            self.create_sign_values(sign_request_3_roles.template_id.sign_item_ids, sign_request_item_signer_2.role_id.id)
        )
        # Assertions after signing the employee sign request item
        self.assertEqual(sign_request_item_signer_1.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_2.state, 'completed', 'The sign.request.item should be completed')
        self.assertEqual(sign_request_item_signer_3.state, 'sent', 'The sign.request.item should be sent')
        completed_document = sign_request_3_roles.get_sign_request_documents()
        self.assertIsNotNone(completed_document, 'The completed document should be available for download.')

    def test_remove_validity_date_of_sign_request(self):
        validity_date = fields.Date.to_date(fields.Date.today()) + timedelta(days=1)
        sign_request = self.create_sign_request_no_item(signer=self.partner_1, cc_partners=self.partner_4, validity=validity_date)
        sign_request.validity = False
        self.assertEqual(sign_request.state, 'sent')

    def test_expired_shared_sign_requests_are_cleaned_up(self):
        """ Tests that the expired sign requests are cleaned when the autovacuum job is called """

        with freeze_time("2025-05-16"):
            shared_request = self.env["sign.request"].create({
                'template_id': self.template_1_role.id,
                'reference': self.template_1_role.display_name,
                'request_item_ids': [Command.create({
                    'role_id': self.role_signer_1.id,
                })],
                'state': 'shared',
                'validity': fields.Date.today() + relativedelta(days=3)
            })

        with freeze_time("2025-05-20"):
            with self.enter_registry_test_mode():
                autovacuum_job = self.env.ref('base.autovacuum_job')
                if autovacuum_job:
                    autovacuum_job.method_direct_trigger()
                    self.assertFalse(shared_request.exists(), "The template is not shared anymore.")

    def test_sign_request_item_value_cannot_be_changed_after_create(self):
        """ Tests that a constant sign item can be created but its value cannot be not modified """
        constant_sign_request = self.create_sign_request_with_constant_field(
            customer=self.partner_1,
            cc_partners=self.partner_4
        )

        role2sign_request_item = {
            sign_request_item.role_id: sign_request_item
            for sign_request_item in constant_sign_request.request_item_ids
        }

        sign_request_item_customer = role2sign_request_item[self.role_1]

        with self.assertRaisesRegex(UserError, "Cannot update the value of a read-only sign item"):
            sign_request_item_customer.sign(self.create_sign_values(constant_sign_request.template_id.sign_item_ids, sign_request_item_customer.role_id.id))

    def test_send_reminder_without_set_validity(self):
        with self.mock_datetime_and_now("2025-07-06"):
            sign_request = self.create_sign_request_3_roles(signer_1=self.partner_1, signer_2=self.partner_2, signer_3=self.partner_3, cc_partners=self.partner_4)
            sign_request.write({'validity': None, 'reminder_enabled': True, 'reminder': 1})

        with self.mock_datetime_and_now("2025-07-07"):
            self.env['sign.request']._cron_reminder()

    def test_signing_order(self):
        wizard = Form(
            self.env['sign.send.request'].with_context(
                default_template_id=self.template_3_roles.id,
                sign_directly_without_mail=False,
            )
        )
        wizard.set_sign_order = True
        self.assertEqual(
            [record['mail_sent_order'] for record in wizard.signer_ids._records],
            [1, 2, 3],
        )
        request = wizard.save()
        request.signer_ids[0].mail_sent_order = 3
        request.signer_ids[1].mail_sent_order = 2
        request.signer_ids[2].mail_sent_order = 1
        wizard = Form(request)
        wizard.save()
        self.assertEqual(
            [s.mail_sent_order for s in request.signer_ids],
            [3, 2, 1],
        )
