from odoo.addons.helpdesk.tests.common import HelpdeskCommon
from odoo.addons.mail.tests.common import MailCommon
from odoo.addons.test_mail.data.test_mail_data import MAIL_TEMPLATE
from odoo.tests import tagged, users
from odoo.tools import formataddr
from odoo.fields import Command


@tagged('post_install', '-at_install', 'mail_flow', 'mail_tools')
class TestHelpdeskMailFeatures(HelpdeskCommon, MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # set high threshold to be sure to not hit mail limit during tests for a model
        cls.env['ir.config_parameter'].sudo().set_param('mail.gateway.loop.threshold', 50)

        # test partners
        cls.partner_1, cls.partner_2, cls.partner_3 = cls.env['res.partner'].create([
            {
                'email': 'valid.lelitre@agrolait.com',
                'name': 'Valid Lelitre',
            }, {
                'email': 'valid.other@gmail.com',
                'name': 'Valid Poilvache',
            }, {
                'email': 'valid.poilboeuf@gmail.com',
                'name': 'Valid Poilboeuf',
            }
        ])

        # be sure to test emails
        cls.user_employee.notification_type = 'email'
        cls.helpdesk_user.notification_type = 'email'
        cls.helpdesk_manager.notification_type = 'inbox'

        # setup alias configuration for test team
        cls.ticket_alias = cls.env['mail.alias'].create({
            'alias_contact': 'everyone',
            'alias_defaults': "{'team_id': %s}" % cls.test_team.id,
            'alias_domain_id': cls.mail_alias_domain.id,
            'alias_model_id': cls.env['ir.model']._get_id('helpdesk.ticket'),
            'alias_name': 'helpdesk',
            'alias_parent_model_id': cls.env['ir.model']._get_id('helpdesk.team'),
            'alias_parent_thread_id': cls.test_team.id,
        })

        # simple template used in auto acknowledgement
        cls.test_template = cls.env['mail.template'].create({
            'auto_delete': True,
            'body_html': '<p>Hello <t t-out="object.partner_id.name"/></p>',
            'email_from': '{{ (object.team_id.alias_email_from or object.company_id.email_formatted or object.user_id.email_formatted or user.email_formatted) }}',
            'lang': '{{ object.partner_id.lang or object.user_id.lang or user.lang }}',
            'model_id': cls.env['ir.model']._get_id('helpdesk.ticket'),
            'name': 'Test Acknowledge',
            'subject': 'Test Acknowledge {{ object.name }}',
            'use_default_to': True,
        })
        cls.stage_new.template_id = cls.test_template.id

        # add some project followers to check followers propagation notably
        cls.test_team.message_subscribe(
            partner_ids=cls.helpdesk_user.partner_id.ids,
            # follow 'new tickets' to receive notification for incoming emails directly
            subtype_ids=(cls.env.ref('mail.mt_comment') + cls.env.ref('helpdesk.mt_team_ticket_new')).ids
        )

    def test_assert_initial_values(self):
        """ Check base values coherency for tests clarity """
        self.assertEqual(
            self.test_team.message_partner_ids,
            self.helpdesk_user.partner_id)

        # check for partner creation, should not pre-exist
        self.assertFalse(self.env['res.partner'].search(
            [('email_normalized', 'in', {'new.cc@test.agrolait.com', 'new.customer@test.agrolait.com', 'new.author@test.agrolait.com'})])
        )

    def test_mailgateway_multicompany(self):
        company0 = self.env.company
        company1 = self.env['res.company'].create({'name': 'new_company0'})
        Partner = self.env['res.partner']

        self.env.user.write({
            'company_ids': [(4, company0.id, False), (4, company1.id, False)],
        })

        team0, team1 = self.env['helpdesk.team'].create([
            {'name': 'helpdesk team 0', 'company_id': company0.id, 'alias_name': 'helpdesk_team_0'},
            {'name': 'helpdesk team 1', 'company_id': company1.id, 'alias_name': 'helpdesk_team_1'},
        ])
        mail_alias0 = team0.alias_id
        mail_alias1 = team1.alias_id
        self.assertEqual((mail_alias0 + mail_alias1).alias_domain_id, self.mail_alias_domain)

        self.assertFalse(self.env['res.partner'].search([('email_normalized', 'in', ['client_a@someprovider.com', 'client_b@someprovider.com'])]))
        tickets = []
        for email_from, email_to in [
            ('A client <client_a@someprovider.com>', mail_alias0.display_name),
            ('B client <client_b@someprovider.com>', mail_alias1.display_name),
        ]:
            with self.mock_mail_gateway():
                tickets.append(self.format_and_process(
                    MAIL_TEMPLATE, email_from, email_to,
                    subject=f'Test from {email_from}',
                    target_model='helpdesk.ticket',
                ))
        helpdesk_ticket0, helpdesk_ticket1 = tickets

        self.assertEqual(helpdesk_ticket0.team_id, team0)
        self.assertEqual(helpdesk_ticket1.team_id, team1)

        self.assertEqual(helpdesk_ticket0.company_id, company0)
        self.assertEqual(helpdesk_ticket1.company_id, company1)

        partner0 = Partner.search([('email', '=', 'client_a@someprovider.com')])
        partner1 = Partner.search([('email', '=', 'client_b@someprovider.com')])
        self.assertTrue(partner0)
        self.assertTrue(partner1)

        self.assertEqual(partner0.company_id, company0)
        self.assertEqual(partner1.company_id, company1)

        self.assertEqual(partner0.name, "A client")
        self.assertEqual(partner1.name, "B client")

        self.assertEqual(helpdesk_ticket0.partner_id, partner0)
        self.assertEqual(helpdesk_ticket1.partner_id, partner1)

        self.assertTrue(partner0 in helpdesk_ticket0.message_partner_ids)
        self.assertTrue(partner1 in helpdesk_ticket1.message_partner_ids)

        # Test case: partner already existing in company A sends email to team alias in company B.
        partner_client_a = Partner.search([('email', 'in', ['client_a@someprovider.com'])])
        self.assertEqual(partner_client_a.company_id, company0)

        with self.mock_mail_gateway():
            helpdesk_ticket_cross = self.format_and_process(
                MAIL_TEMPLATE,
                'A client <client_a@someprovider.com>',
                mail_alias1.display_name,
                subject='Cross-company ticket',
                target_model='helpdesk.ticket',
            )

        self.assertEqual(helpdesk_ticket_cross.team_id, team1)
        self.assertEqual(helpdesk_ticket_cross.company_id, company1)
        self.assertEqual(helpdesk_ticket_cross.partner_id.company_id, company1, "A new partner should have been created in company of helpdesk team.")
        self.assertTrue(helpdesk_ticket_cross.partner_id in helpdesk_ticket_cross.message_follower_ids.mapped('partner_id'))

    def test_mailgateway_with_template(self):
        """ Portal / internal users receive an email when they create a ticket """
        internal_followers = self.helpdesk_user.partner_id
        new_partner_email = '"New Author" <new.author@test.agrolait.com>'

        incoming_cc = f'"New Cc" <new.cc@test.agrolait.com>, {self.partner_2.email_formatted}'
        incoming_to = f'{self.ticket_alias.alias_full_name}, {self.partner_1.email_formatted}, "New Customer" <new.customer@test.agrolait.com>'
        incoming_to_filtered = f'{self.partner_1.email_formatted}, "New Customer" <new.customer@test.agrolait.com>'
        for test_user in (self.user_employee, self.helpdesk_portal, False):
            with self.subTest(user_name=test_user.name if test_user else new_partner_email):
                email_from = test_user.email_formatted if test_user else new_partner_email
                with self.mock_mail_gateway():
                    ticket = self.format_and_process(
                        MAIL_TEMPLATE, email_from,
                        incoming_to,
                        cc=incoming_cc,
                        subject=f'Test from {email_from}',
                        target_model='helpdesk.ticket',
                    )
                    self.flush_tracking()

                if test_user:
                    author = test_user.partner_id
                else:
                    author = self.env['res.partner'].search([('email_normalized', '=', 'new.author@test.agrolait.com')])
                    self.assertTrue(author, 'Helpdesk automatically creates a partner for incoming email')
                    self.assertEqual(author.email, 'new.author@test.agrolait.com', 'Should parse name/email correctly')
                    self.assertEqual(author.name, 'New Author', 'Should parse name/email correctly')

                # converts Cc into partner due to '_message_get_default_recipients'
                # that checks for 'email_cc' field
                new_partner_cc = self.env['res.partner'].search([('email_normalized', '=', 'new.cc@test.agrolait.com')])
                self.assertTrue(new_partner_cc)
                self.assertEqual(new_partner_cc.email, 'new.cc@test.agrolait.com')
                # self.assertEqual(new_partner_cc.name, 'New Cc')
                self.assertEqual(new_partner_cc.name, 'new.cc@test.agrolait.com', 'TDE FIXME: name incorrectly parsed')
                # do not convert other people in To, simply recognized if they exist
                new_partner_to = self.env['res.partner'].search([('email_normalized', '=', 'new.customer@test.agrolait.com')])
                self.assertEqual(new_partner_to.email, 'new.customer@test.agrolait.com')
                self.assertEqual(new_partner_to.name, 'new.customer@test.agrolait.com', 'TDE FIXME: name incorrectly parsed')

                expected_chatter_reply_to = formataddr(
                    (author.name, self.ticket_alias.alias_full_name)
                )

                self.assertIn('Please call me as soon as possible', ticket.description)
                self.assertEqual(ticket.email_cc, f'"New Cc" <new.cc@test.agrolait.com>, {self.partner_2.email_formatted}')
                self.assertEqual(ticket.name, f'Test from {author.email_formatted}')
                self.assertEqual(ticket.partner_id, author)
                self.assertEqual(ticket.stage_id, self.stage_new)
                self.assertEqual(ticket.team_id, self.test_team)
                # followers
                self.assertEqual(
                    ticket.message_partner_ids,
                    internal_followers + author + self.partner_1 + self.partner_2 + new_partner_cc + new_partner_to,
                    'Helpdesk subscribes about everyone in the world to tickets')
                # check that when a portal user creates a ticket there is two message on the ticket:
                # - the creation message email
                # - the mail from the stage mail template
                self.assertEqual(len(ticket.message_ids), 2)
                # first message: incoming email: sent to email followers
                incoming_email = ticket.message_ids[1]
                self.assertMailNotifications(
                    incoming_email,
                    [
                        {
                            'content': 'Please call me as soon as possible',
                            'email_values': {
                                'email_from': formataddr((author.name, author.email_normalized)),
                            },
                            'message_type': 'email',
                            'message_values': {
                                # ticket creates a partner that if then found by mailgateway
                                'author_id': author,
                                'email_from': formataddr((author.name, author.email_normalized)),
                                # coming from incoming email
                                'incoming_email_cc': incoming_cc,
                                'incoming_email_to': incoming_to_filtered,
                                'mail_server_id': self.env['ir.mail_server'],
                                # followers of 'new task' subtype (but not original To as they
                                # already received the email)
                                'notified_partner_ids': internal_followers,
                                # deduced from 'To' and 'Cc' (recognized partners)
                                'partner_ids': self.partner_1 + self.partner_2,
                                'parent_id': self.env['mail.message'],
                                'reply_to': expected_chatter_reply_to,
                                'subject': f'Test from {author.email_formatted}',
                                'subtype_id': self.env.ref('helpdesk.mt_ticket_new'),
                            },
                            'notif': [
                                {'partner': self.helpdesk_user.partner_id, 'type': 'email',},
                            ],
                        },
                    ],
                )

                # second message: acknowledgment: sent to email author
                acknowledgement = ticket.message_ids[0]
                # task created by odoobot if not incoming user -> odoobot author of ack email
                acknowledgement_author = test_user.partner_id if test_user else self.partner_root
                self.assertMailNotifications(
                    acknowledgement,
                    [
                        {
                            'content': f'Hello {author.name}',
                            'email_values': {
                                # be sure to check email_from of outgoing email not based on author_id
                                'email_from': self.test_team.alias_email_from,
                            },
                            'message_type': 'auto_comment',
                            'message_values': {
                                'author_id': acknowledgement_author,
                                'email_from': self.test_team.alias_email_from,
                                'incoming_email_cc': False,
                                'incoming_email_to': False,
                                'mail_server_id': self.env['ir.mail_server'],
                                # default recipients: partner_id, no note followers
                                'notified_partner_ids': author,
                                # default recipients: partner_id
                                'partner_ids': author,
                                'parent_id': incoming_email,
                                'reply_to': formataddr((
                                    acknowledgement_author.name, self.ticket_alias.alias_full_name,
                                )),
                                'subject': f'Test Acknowledge {ticket.name}',
                                # subtype from '_track_template'
                                'subtype_id': self.env.ref('mail.mt_note'),
                            },
                            'notif': [
                                # specific email for portal customer, due to portal mixin
                                {'partner': author, 'type': 'email', 'group': 'portal_customer',},
                            ],
                        },
                    ],
                )

                # uses Chatter: fetches suggested recipients, post a message
                # - checks all suggested: incoming email to + cc are included
                # - for all notified people: expected 'email_to' is them
                # ------------------------------------------------------------
                suggested_all = ticket.with_user(self.helpdesk_user)._message_get_suggested_recipients(
                    reply_discussion=True, no_create=False,
                )
                # ticket creates partners and followers for everyone, hence no suggested people :()
                # except customer if shared, even if already follower
                if test_user == self.helpdesk_portal:
                    expected_all = [
                        {
                            'create_values': {},
                            'email': self.helpdesk_portal.email_normalized,
                            'name': self.helpdesk_portal.name,
                            'partner_id': self.helpdesk_portal.partner_id.id,
                        },
                    ]
                elif not test_user:
                    expected_all = [
                        {
                            'create_values': {},
                            'email': author.email_normalized,
                            'name': author.name,
                            'partner_id': author.id,
                        },
                    ]
                else:
                    expected_all = []
                self.assertEqual(suggested_all, expected_all)

                # finally post the message with recipients
                with self.mock_mail_gateway():
                    responsible_answer = ticket.with_user(self.helpdesk_user).message_post(
                        body='<p>Well received !',
                        partner_ids=[],
                        message_type='comment',
                        subject=f'Re: {ticket.name}',
                        subtype_id=self.env.ref('mail.mt_comment').id,
                    )
                external_partners = self.partner_1 + self.partner_2 + new_partner_cc + new_partner_to
                self.assertEqual(ticket.message_partner_ids, internal_followers + author + external_partners)

                expected_answer_reply_to = formataddr((self.helpdesk_user.name, self.ticket_alias.alias_full_name))
                self.assertMailNotifications(
                    responsible_answer,
                    [
                        {
                            'content': 'Well received !',
                            'mail_mail_values': {
                                'mail_server_id': self.env['ir.mail_server'],  # no specified server
                            },
                            'message_type': 'comment',
                            'message_values': {
                                'author_id': self.helpdesk_user.partner_id,
                                'email_from': self.helpdesk_user.partner_id.email_formatted,
                                'incoming_email_cc': False,
                                'incoming_email_to': False,
                                'mail_server_id': self.env['ir.mail_server'],
                                # helpdesk_user not notified of its own message, even if follower
                                'notified_partner_ids': author + external_partners,
                                'parent_id': incoming_email,
                                # coming from post
                                'partner_ids': self.env['res.partner'],
                                'reply_to': expected_answer_reply_to,
                                'subject': f'Re: {ticket.name}',
                                'subtype_id': self.env.ref('mail.mt_comment'),
                            },
                            'notif': [
                                # original author has a specific email with links and tokens
                                {'partner': author, 'type': 'email', 'group': 'portal_customer'},
                                {'partner': self.partner_1, 'type': 'email'},
                                {'partner': self.partner_2, 'type': 'email'},
                                {'partner': new_partner_cc, 'type': 'email'},
                                {'partner': new_partner_to, 'type': 'email'},
                            ],
                        },
                    ],
                )

                # SMTP emails really sent (not Inbox guy then)
                # expected Msg['To'] : Reply-All behavior: actual recipient, then
                # all "not internal partners" and catchall (to receive answers)
                for partner in responsible_answer.notified_partner_ids:
                    exp_msg_to_partners = partner | external_partners
                    if author != self.user_employee.partner_id:  # external only !
                        exp_msg_to_partners |= author
                    exp_msg_to = exp_msg_to_partners.mapped('email_formatted')
                    with self.subTest(name=partner.name):
                        self.assertSMTPEmailsSent(
                            mail_server=self.mail_server_notification,
                            msg_from=formataddr((self.helpdesk_user.name, f'{self.default_from}@{self.alias_domain}')),
                            smtp_from=self.mail_server_notification.from_filter,
                            smtp_to_list=[partner.email_normalized],
                            msg_to_lst=exp_msg_to,
                        )

                # customer replies using "Reply All" + adds new people
                # ------------------------------------------------------------
                self.gateway_mail_reply_from_smtp_email(
                    MAIL_TEMPLATE, [author.email_normalized], reply_all=True,
                    cc=f'"Another Cc" <another.cc@test.agrolait.com>, {self.partner_3.email}',
                    target_model='helpdesk.ticket',
                )
                self.assertEqual(
                    ticket.email_cc,
                    '"Another Cc" <another.cc@test.agrolait.com>, valid.poilboeuf@gmail.com, "New Cc" <new.cc@test.agrolait.com>, "Valid Poilvache" <valid.other@gmail.com>',
                    'Updated with new Cc')
                self.assertEqual(len(ticket.message_ids), 4, 'Incoming email + acknowledgement + chatter reply + customer reply')
                self.assertEqual(
                    ticket.message_partner_ids,
                    internal_followers + author + self.partner_1 + self.partner_2 + self.partner_3 + new_partner_cc + new_partner_to)

                self.assertMailNotifications(
                    ticket.message_ids[0],
                    [
                        {
                            'content': 'Please call me as soon as possible',
                            'message_type': 'email',
                            'message_values': {
                                'author_id': author,
                                'email_from': author.email_formatted,
                                # coming from incoming email
                                'incoming_email_cc': f'"Another Cc" <another.cc@test.agrolait.com>, {self.partner_3.email}',
                                # To: received email Msg-To - customer who replies, without email Reply-To
                                'incoming_email_to': ', '.join(external_partners.mapped('email_formatted')),
                                'mail_server_id': self.env['ir.mail_server'],
                                # notified: followers - already emailed, aka internal only
                                'notified_partner_ids': internal_followers,
                                'parent_id': responsible_answer,
                                # same reasoning as email_to/cc
                                'partner_ids': external_partners + self.partner_3,
                                'subject': f'Re: Re: {ticket.name}',
                                'subtype_id': self.env.ref('mail.mt_comment'),
                            },
                            'notif': [
                                {'partner': self.helpdesk_user.partner_id, 'type': 'email',},
                            ],
                        },
                    ],
                )

                # clear for other loops
                (new_partner_cc + new_partner_to).unlink()

    def test_mailgateway_without_template(self):
        """ A mail sent to the alias without mail template on the stage should also create a partner """
        self.stage_new.template_id = False

        with self.mock_mail_gateway():
            ticket = self.format_and_process(
                MAIL_TEMPLATE,
                '"New Customer" <new.customer@test.example.com>',
                self.ticket_alias.alias_full_name,
                subject='Test Send from email',
                target_model='helpdesk.ticket',
            )
        self.flush_tracking()
        self.assertIn('Please call me as soon as possible this afternoon!', ticket.description,
                      "the email body should be in the ticket's description")
        self.assertEqual(ticket.message_partner_ids, ticket.partner_id + self.helpdesk_user.partner_id)
        self.assertEqual(ticket.name, 'Test Send from email')
        self.assertTrue(ticket.partner_id)
        self.assertEqual(ticket.partner_id.name, 'New Customer')

    @users('hm')
    def test_suggested_recipients_auto_creation(self):
        """Check default creates value for auto creation of recipient (customer)."""
        partner_name = 'Jérémy Dawson'
        partner_phone = '+33 1990b01010'
        email = 'jdawson@example.com'
        formatted_email = formataddr((partner_name, email))
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'How do I renew my subscription at the discounted price?',
            'partner_phone': partner_phone,
            'partner_name': partner_name,
        })
        ticket.partner_email = formatted_email
        data = ticket._message_get_suggested_recipients(no_create=True)[0]
        self.assertEqual(data['email'], email)
        self.assertEqual(data['name'], partner_name)
        self.assertDictEqual(data['create_values'], {'company_id': self.helpdesk_manager.company_id.id, 'phone': partner_phone})

    def test_ticket_create_ticket_email_cc(self):
        ''' Make sure creating a ticket with an email_cc field creates a follower. '''
        ticket = self.env['helpdesk.ticket'].create({
            'partner_name': 'Test Name',
            'partner_email': 'testmail@test.com',
            'name': 'Ticket Name',
            'email_cc': 'testcc@test.com',
        })
        follow = self.env['mail.followers'].search([
            ('res_model', '=', 'helpdesk.ticket'),
            ('res_id', '=', ticket.id),
        ], limit=1)
        self.assertTrue(follow)

    def test_ticket_portal_share_adds_followers(self):
        """ Test that sharing a ticket through the portal share wizard adds recipients as followers.

            Test Cases:
            ===========
            1) Create a test ticket.
            2) Verify that the portal user is not a follower of the ticket.
            3) Create and execute a portal share wizard to share the ticket with the portal user.
            4) Verify that the portal user has been added as a follower after sharing.
        """

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Ticket to Share',
            'team_id': self.test_team.id,
        })

        self.assertNotIn(self.helpdesk_portal.partner_id, ticket.message_partner_ids,
                        "Portal user's partner should not be a follower initially")

        share_wizard = self.env['portal.share'].create({
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'partner_ids': [Command.set(self.helpdesk_portal.partner_id.ids)]
        })

        with self.mock_mail_gateway():
            share_wizard.action_send_mail()

        self.assertIn(self.helpdesk_portal.partner_id, ticket.message_partner_ids,
                    "Portal user's partner should be added as a follower after sharing")

    def test_ticket_creation_removes_email_signatures(self):
        """
        Tests that email signature is correctly removed from a ticket
        description when a ticket is created from an email alias.
        """

        gmail_email_source = f"""From: {self.partner_1.email_formatted}
To: {self.test_team.alias_id.alias_full_name}
Subject: Test Gmail Signature Removal
Content-Type: text/html;

<p>This is the main helpdesk ticket content.</p>
<span>--</span>
<div data-smartmail="gmail_signature">
<p>Valid Lelitre</p>
<p>Concerned Customer</p>
</div>
"""

        outlook_email_source = f"""From: {self.partner_2.email_formatted}
To: {self.test_team.alias_id.alias_full_name}
Subject: Test Outlook Signature Removal
Content-Type: text/html;

<p>This is the main helpdesk ticket content.</p>
<div id="Signature">
<p>Valid Poilvache</p>
<p>Valued Client</p>
</div>
"""
        with self.mock_mail_gateway():
            gmail_ticket_id = self.env['mail.thread'].message_process(
                model='helpdesk.ticket',
                message=gmail_email_source,
                custom_values={'team_id': self.test_team.id}
            )
            outlook_ticket_id = self.env['mail.thread'].message_process(
                model='helpdesk.ticket',
                message=outlook_email_source,
                custom_values={'team_id': self.test_team.id}
            )

        # 1. Verify Gmail signature removal
        self.assertTrue(gmail_ticket_id, "Gmail ticket creation should return a valid ID.")
        gmail_ticket = self.env['helpdesk.ticket'].browse(gmail_ticket_id)

        self.assertIn("This is the main helpdesk ticket content", gmail_ticket.description, "The main content should be present.")
        self.assertNotIn("--", gmail_ticket.description, "The Gmail signature separator should have been removed.")
        self.assertNotIn("Valid Lelitre", gmail_ticket.description, "The Gmail signature should have been removed.")
        self.assertNotIn("Concerned Customer", gmail_ticket.description, "The Gmail signature should have been removed.")

        # 2. Verify Outlook signature removal
        self.assertTrue(outlook_ticket_id, "Outlook ticket creation should return a valid ID.")
        outlook_ticket = self.env['helpdesk.ticket'].browse(outlook_ticket_id)

        self.assertIn("This is the main helpdesk ticket content", outlook_ticket.description, "The main content should be present.")
        self.assertNotIn("Valid Poilvache", outlook_ticket.description, "The Outlook signature should have been removed.")
        self.assertNotIn("Valued Client", outlook_ticket.description, "The Outlook signature should have been removed.")
