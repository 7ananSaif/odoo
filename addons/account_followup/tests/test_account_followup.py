from unittest.mock import patch
from freezegun import freeze_time
from odoo import Command, fields
from odoo.tests import tagged
from odoo.addons.account_followup.tests.common import TestAccountFollowupCommon
from odoo.addons.mail.tests.common import MailCommon
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestAccountFollowupReports(TestAccountFollowupCommon, MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['account_followup.followup.line'].search([]).unlink()

        wkhtmltopdf_patcher = patch.object(
            cls.env.registry['ir.actions.report'],
            '_run_wkhtmltopdf',
            lambda *args, **kwargs: b"0"
        )
        wkhtmltopdf_patcher.start()
        cls.addClassCleanup(wkhtmltopdf_patcher.stop)

    def create_followup(self, delay):
        return self.env['account_followup.followup.line'].create({
            'name': f'followup {delay}',
            'delay': delay,
            'send_email': False,
            'company_id': self.company_data['company'].id
        })

    def create_invoice(self, date, partner = None):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': date,
            'invoice_date_due': date,
            'partner_id': partner.id if partner else self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500,
                'tax_ids': [],
            })]
        })
        invoice.action_post()
        return invoice

    def test_followup_responsible(self):
        """
        Test that the responsible is correctly set
        """
        self.first_followup_line = self.create_followup(delay=-10)

        user1 = self.env['res.users'].create({
            'name': 'A User',
            'login': 'a_user',
            'email': 'a@user.com',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])]
        })
        user2 = self.env['res.users'].create({
            'name': 'Another User',
            'login': 'another_user',
            'email': 'another@user.com',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])]
        })
        # 1- no info, use current user
        self.assertEqual(self.partner_a._get_followup_responsible(), self.env.user)

        # 2- set invoice user
        invoice1 = self.init_invoice('out_invoice', partner=self.partner_a,
                                     invoice_date=fields.Date.from_string('2000-01-01'),
                                     amounts=[2000])
        invoice2 = self.init_invoice('out_invoice', partner=self.partner_a,
                                     invoice_date=fields.Date.from_string('2000-01-01'),
                                     amounts=[1000])
        invoice1.invoice_user_id = user1
        invoice2.invoice_user_id = user2
        (invoice1 + invoice2).action_post()
        # Should pick invoice_user_id of the most delayed move, with highest residual amount in case of tie (invoice1)
        self.assertEqual(self.partner_a._get_followup_responsible(), user1)
        # If user1 is archived, it shouldn't be selected as responsible
        user1.active = False
        self.assertEqual(self.partner_a._get_followup_responsible(), self.env.user)
        user1.active = True

        self.partner_a.followup_line_id = self.first_followup_line

        # 3- A followup responsible user has been set on the partner
        self.partner_a.followup_responsible_id = user2
        self.assertEqual(self.partner_a._get_followup_responsible(), user2)

        # 4- Modify the default responsible on followup level
        self.partner_a.followup_line_id.activity_default_responsible_type = 'salesperson'
        self.assertEqual(self.partner_a._get_followup_responsible(), user1)
        self.assertEqual(self.partner_a._get_followup_responsible(multiple_responsible=True), (user1 + user2))

        self.partner_a.followup_line_id.activity_default_responsible_type = 'account_manager'
        self.partner_a.user_id = user2
        self.assertEqual(self.partner_a._get_followup_responsible(), self.partner_a.user_id)

    def test_followup_activity(self):
        first_followup_line = self.create_followup(delay=10)
        first_followup_line.create_activity = True
        first_followup_line.activity_default_responsible_type = 'salesperson'
        user1 = self.env['res.users'].create({
            'name': 'A User',
            'login': 'a_user',
            'email': 'a@user.com',
            'group_ids': [Command.set([self.env.ref('account.group_account_user').id])]
        })
        user2 = self.env['res.users'].create({
            'name': 'Another User',
            'login': 'another_user',
            'email': 'another@user.com',
            'group_ids': [Command.set([self.env.ref('account.group_account_user').id])]
        })
        inv1 = self.create_invoice('2022-01-02')
        inv1.invoice_user_id = user1
        inv2 = self.create_invoice('2022-01-02')
        inv2.invoice_user_id = user2

        with freeze_time('2022-01-13'):
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertEqual(self.partner_a.activity_ids.user_id, (user1 + user2))

    def test_followup_no_invoice_user_id(self):
        first_followup_line = self.create_followup(delay=10)
        first_followup_line.create_activity = True
        first_followup_line.activity_default_responsible_type = 'salesperson'
        inv1 = self.create_invoice('2022-01-02')
        inv1.invoice_user_id = None
        with freeze_time('2022-01-13'):
            self.assertEqual(self.partner_a._get_followup_responsible(), self.user)

    def test_followup_line_and_status(self):
        self.first_followup_line = self.create_followup(delay=-10)
        self.second_followup_line = self.create_followup(delay=10)
        self.third_followup_line = self.create_followup(delay=15)

        self.create_invoice('2022-01-02')

        with freeze_time('2021-12-20'):
            # Today < due date + delay first followup level (negative delay -> reminder before due date)
            self.assertPartnerFollowup(self.partner_a, 'no_action_needed', self.first_followup_line)

        with freeze_time('2021-12-24'):
            # Today = due date + delay first followup level
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.first_followup_line)

            # followup_next_action_date not exceeded but no invoice is overdue,
            # we should not be in status 'with_overdue_invoices' but 'no action needed'
            self.partner_a.followup_next_action_date = fields.Date.from_string('2021-12-25')
            self.assertPartnerFollowup(self.partner_a, 'no_action_needed', self.first_followup_line)

        with freeze_time('2022-01-13'):
            # Today > due date + delay second followup level but first followup level not processed yet
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.first_followup_line)

            self.partner_a._execute_followup_partner(options={'snailmail': False})
            # Due date exceeded but first followup level processed
            # followup_next_action_date set in 20 days (delay 2nd level - delay 1st level = 10 - (-10) = 20)
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', self.second_followup_line)
            self.assertEqual(self.partner_a.followup_next_action_date, fields.Date.from_string('2022-02-02'))

        with freeze_time('2022-02-03'):
            # followup_next_action_date exceeded and invoice not reconciled yet
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.second_followup_line)
            # execute second followup
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', self.third_followup_line)
            self.assertEqual(self.partner_a.followup_next_action_date, fields.Date.from_string('2022-02-08'))

        with freeze_time('2022-02-09'):
            # followup_next_action_date exceeded and invoice not reconciled yet
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.third_followup_line)
            # execute third followup
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', self.third_followup_line)
            self.assertEqual(self.partner_a.followup_next_action_date, fields.Date.from_string('2022-02-14'))

        with freeze_time('2022-02-15'):
            # followup_next_action_date exceeded and invoice not reconciled yet
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', self.third_followup_line)
            # executing the third followup again should do nothing as all the aml are linked to it
            followup_executed = self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertFalse(followup_executed)

            # create a new overdue invoice
            self.create_invoice('2022-01-03')
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.third_followup_line)

            aml_ids = self.partner_a.unreconciled_aml_ids

            # Exclude every unreconciled invoice line.
            aml_ids.no_followup = True
            # Every unreconciled invoice line is excluded, so the result should be `no_action_needed`.
            self.assertPartnerFollowup(self.partner_a, 'no_action_needed', self.third_followup_line)

            # It resets if we don't exclude them anymore.
            aml_ids.no_followup = False
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', self.third_followup_line)

            self.env['account.payment.register'].create({
                'line_ids': self.partner_a.unreconciled_aml_ids,
            })._create_payments()
            self.assertPartnerFollowup(self.partner_a, None, None)

    def test_followup_multiple_invoices(self):
        followup_10 = self.create_followup(delay=10)
        followup_15 = self.create_followup(delay=15)
        followup_30 = self.create_followup(delay=30)

        self.create_invoice('2022-01-01')
        self.create_invoice('2022-01-02')

        # 9 days are not passed yet for the first followup level, current delay is 10-0=10
        with freeze_time('2022-01-10'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # 10 days passed, current delay is 10-0=10, need to take action
        with freeze_time('2022-01-11'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

        # action taken 4 days ago, current delay is 15-10=5, nothing needed
        with freeze_time('2022-01-15'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

        # action taken 5 days ago, current delay is 15-10=5, need to take action
        with freeze_time('2022-01-16'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_15)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

        # action taken 14 days ago, current delay is 30-15=15, nothing needed
        with freeze_time('2022-01-30'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

        # action taken 15 days ago, current delay is 30-15=15, need to take action
        with freeze_time('2022-01-31'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_30)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

        # action taken 13 days ago, current delay is 15 (same on repeat), nothing needed
        with freeze_time('2022-02-14'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

        # action taken 14 days ago, current delay is 15 (same on repeat), need to take action
        with freeze_time('2022-02-15'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_30)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

    def test_followup_multiple_invoices_with_first_payment(self):
        # Test the behavior of multiple invoices when the first one is paid
        followup_10 = self.create_followup(delay=10)
        followup_15 = self.create_followup(delay=15)

        invoice_01 = self.create_invoice('2022-01-01')
        self.create_invoice('2022-01-02')

        # 9 days are not passed yet for the first followup level, current delay is 10-0=10
        with freeze_time('2022-01-10'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # 10 days passed, current delay is 10-0=10, need to take action
        with freeze_time('2022-01-11'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            # followup level for the second invoice shouldn't change since it's only 9 days overdue
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

            self.env['account.payment.register'].create({
                'line_ids': invoice_01.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

            # partner followup level goes back to 10 days after paying the first invoice
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # action taken 4 days ago, current delay is 15-10=5, nothing needed
        with freeze_time('2022-01-15'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # action taken 5 days ago, current delay is 15-10=5, need to take action
        with freeze_time('2022-01-16'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

    def test_followup_multiple_invoices_with_last_payment(self):
        # Test the behavior of multiple invoices when the last one is paid
        # Should behave exactly like test_followup_multiple_invoices_with_first_payment
        # because the followup is done at the same time.
        followup_10 = self.create_followup(delay=10)
        followup_15 = self.create_followup(delay=15)
        followup_30 = self.create_followup(delay=30)

        self.create_invoice('2022-01-01')
        invoice_02 = self.create_invoice('2022-01-02')

        # 9 days are not passed yet for the first followup level, current delay is 10-0=10
        with freeze_time('2022-01-10'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # 10 days passed, current delay is 10-0=10, need to take action
        with freeze_time('2022-01-11'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

            self.env['account.payment.register'].create({
                'line_ids': invoice_02.line_ids.filtered(lambda l: l.display_type == 'payment_term'),
            })._create_payments()

            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

        # action taken 4 days ago, current delay is 15-10=5, nothing needed
        with freeze_time('2022-01-15'):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_15)

        # action taken 5 days ago, current delay is 15-10=5, need to take action
        with freeze_time('2022-01-16'):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_15)
            self.partner_a._execute_followup_partner(options={'snailmail': False})
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_30)

    def test_followup_status_entry_lines(self):
        """
            Creating an entry should not affect the followups as there is no concept of due date with this flow.
        """
        self.followup_line = self.create_followup(delay=10)

        with freeze_time('2022-01-02'):
            invoice = self.env['account.move'].create({
                'move_type': 'entry',
                'date': fields.Date.from_string('2022-01-02'),
                'partner_id': self.partner_a.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'line1',
                        'account_id': self.company_data['default_account_revenue'].id,
                        'debit': 500.0,
                        'credit': 0.0,
                    }),
                    Command.create({
                        'name': 'counterpart line',
                        'account_id': self.company_data['default_account_receivable'].id,
                        'debit': 0.0,
                        'credit': 500.0,
                    })
                ]
            })
            invoice.action_post()

        with freeze_time('2022-01-13'):
            self.assertPartnerFollowup(self.partner_a, 'no_action_needed', self.followup_line)

    def test_followup_contacts(self):
        followup_contacts = self.partner_a._get_all_followup_contacts()
        billing_contact = self.env['res.partner'].browse(self.partner_a.address_get(['invoice'])['invoice'])
        self.assertEqual(billing_contact, followup_contacts)

    def test_followup_cron(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        followup_10 = self.create_followup(delay=10)
        followup_10.auto_execute = True

        self.create_invoice('2022-01-01')

        # Check that no followup is automatically done if there is no action needed
        with (
            freeze_time('2022-01-10'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)
            cron.method_direct_trigger()
            patched.assert_not_called()
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

        # Check that the action is taken one and only one time when there is an action needed
        with (
            freeze_time('2022-01-11'),
            patch.object(self.env.registry['res.partner'], '_send_followup') as patched,
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, 'in_need_of_action', followup_10)
            cron.method_direct_trigger()
            patched.assert_called_once()
            self.assertPartnerFollowup(self.partner_a, 'with_overdue_invoices', followup_10)

    def test_onchange_residual_amount(self):
        '''
        Test residual onchange on account move lines: the residual amount is
        computed using an sql query. This test makes sure the computation also
        works properly during onchange (on records having a NewId).
        '''
        invoice = self.create_invoice('2016-01-01')
        self.create_invoice('2016-01-02')

        self.env['account.payment.register'].with_context(active_ids=invoice.ids, active_model='account.move').create({
            'payment_date': invoice.date,
            'amount': 100,
        })._create_payments()

        self.assertRecordValues(self.partner_a, [{'total_due': 900.0}])
        self.assertRecordValues(self.partner_a.unreconciled_aml_ids.sorted(), [
            {'amount_residual_currency': 500.0},
            {'amount_residual_currency': 400.0},
        ])

        self.assertRecordValues(self.partner_a.unreconciled_aml_ids.sorted(), [
            {'amount_residual_currency': 500.0},
            {'amount_residual_currency': 400.0},
        ])

    def test_compute_total_due(self):
        self.create_invoice('2016-01-01')
        self.create_invoice('2017-01-01')
        self.create_invoice(fields.Date.today() + relativedelta(months=1))
        self.env['account.move'].create([{
            'move_type': 'in_invoice',
            'invoice_date': date,
            'partner_id': self.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500,
                'tax_ids': [],
            })]
        } for date in ('2016-01-01', '2017-01-01', fields.Date.today() + relativedelta(months=1))]).action_post()

        self.assertRecordValues(self.partner_a, [{
            'total_due': 1500.0,
            'total_overdue': 1000.0,
            'total_all_due': 0.0,
            'total_all_overdue': 0.0,
        }])

    def test_send_followup_no_due_date(self):
        """
        test sending a followup report with an empty due date field
        """
        self.create_followup(delay=0)
        self.create_invoice('2022-01-01')
        self.partner_a.unreconciled_aml_ids.write({
            'date_maturity': False,
        })

        self.partner_a._execute_followup_partner(options={
            'partner_id': self.partner_a.id,
            'manual_followup': True,
            'snailmail': False,
        })

    def test_followup_copy_data(self):
        """
        Test followup report by:
        - Duplicating a single record with no default
        - Duplicating several records at the same time
        """
        followup_50 = self.create_followup(delay=50)
        followup_60 = self.create_followup(delay=60)

        # Duplicate single record with no default values
        followup_50_duplicate = followup_50.copy()
        self.assertTrue(followup_50_duplicate)
        self.assertEqual(followup_50_duplicate.name, f'75 days (copy of {followup_50.name})')

        # Duplicate multiple records at the same time with no default values
        multiple_followup_records = followup_50 + followup_60
        multiple_followup_records_duplicate = multiple_followup_records.copy()
        self.assertTrue(multiple_followup_records_duplicate)
        self.assertEqual(multiple_followup_records_duplicate[0].name, f'90 days (copy of {followup_50.name})')
        self.assertEqual(multiple_followup_records_duplicate[1].name, f'105 days (copy of {followup_60.name})')

    def test_manual_reminder_get_template_mail_addresses(self):
        """
        When opening account_followup.manual_reminder, the partner should always be in `email_recipients_ids`
        When adding a template, the template's partner_to, email_cc and email_to should be added to `email_recipient_ids` as well
        """
        mail_partner = self.env['res.partner'].create({
            'name': 'Mai Lang',
            'email': 'mail.ang@test.com',
        })
        mail_cc = self.env['res.partner'].create({
            'name': 'John Carmac',
            'email': 'john.carmac@example.me',
        })

        mail_template = self.env['mail.template'].create({
            'name': 'reminder',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'email_cc': mail_cc.email,
            'use_default_to': False,
        })

        reminder = self.env['account_followup.manual_reminder'].with_context(
            active_model='res.partner',
            active_ids=mail_partner.ids,
        ).create({'template_id': mail_template.id})

        self.assertTrue(mail_partner in reminder.email_recipient_ids, "Mai Lang should be in the Email Recipients List")

        reminder.template_id = mail_template

        self.assertTrue(mail_cc in reminder.email_recipient_ids, "John Carmac should be in the Email Recipients list.")
        self.assertTrue(mail_partner in reminder.email_recipient_ids, "Mai Lang should still be in the Email Recipients List")

    def test_overdue_invoices_action_domain_includes_children_partners(self):
        """
        When checking overdue invoices for a company (partner), the action [action_open_overdue_entries] domain should also include
        the overdue invoices of its children partners.
        """

        # Step 1: Create contacts
        parent_contact = self.env['res.partner'].create({
            'name': 'Parent Contact',
            'is_company': True,
        })
        child_contact = self.env['res.partner'].create({
            'name': 'Child Contact',
            'parent_id': parent_contact.id,
        })

        # Step 2: Create an invoice for the child contact
        invoice_date = fields.Date.today() - relativedelta(months=1)
        invoice = self.create_invoice(invoice_date, child_contact)
        invoice.invoice_date_due = invoice_date

        # Step 3: Verify follow-up status and overdue invoices of the parent contact
        action = parent_contact.action_open_overdue_entries()
        overdue_invoices = self.env['account.move'].search(action['domain'])
        self.assertIn(invoice.id, overdue_invoices.ids)
        self.assertEqual(parent_contact.followup_status, 'with_overdue_invoices')

    def test_journal_items_action_domain_filters_partner_posted_entries(self):
        """
        The action [action_open_partner_followup_journal_items] should return journal items
        belonging to the selected partner, only from posted moves, and limited
        to payable/receivable accounts marked as trade (non_trade = False).
        """
        test_partner = self.env['res.partner'].create({
            'name': 'Journal Items with Partner',
            'is_company': True,
            'customer_rank': 1,
        })
        invoice_date = fields.Date.today() - relativedelta(months=1)

        # Create invoices
        normal_invoice = self.create_invoice(fields.Date.today(), test_partner)
        overdue_invoice = self.create_invoice(invoice_date, test_partner)

        action = test_partner.action_open_partner_followup_journal_items()

        # Validate context
        ctx = action["context"]
        self.assertEqual(ctx.get("search_default_partner_id"), [test_partner.id])
        self.assertEqual(ctx.get("search_default_posted"), 1)

        # Either receivable or payable should be set to 1
        self.assertEqual(ctx.get("search_default_trade_receivable"), 1)
        # Non-trade filters should be disabled
        self.assertEqual(ctx.get("search_default_non_trade_receivable"), 0)
        self.assertEqual(ctx.get("search_default_non_trade_payable", 0), 0)

        # Validate domain and results
        aml = self.env["account.move.line"].search(action["domain"])
        self.assertEqual(aml.ids, normal_invoice.line_ids.ids + overdue_invoice.line_ids.ids)

    def test_followup_template_recipients_with_cron(self):
        """
        tests that when a mail_cc is defined on a template,
        even if the action is ran from a cron (and de facto from `res.partner.send_followup_email`)
        the email is correctly sent
        Completes `test_manual_reminder_get_template_mail_addresses`
        """
        self.partner_a.email = "test@test.com"
        mail_cc = self.env['res.partner'].create({
            'name': 'John Carmac',
            'email': 'john.carmac@example.me',
        })
        mail_template = self.env['mail.template'].create({
            'name': 'reminder',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'email_cc': mail_cc.email,
            'use_default_to': False,
        })
        followup_10 = self.create_followup(delay=10)
        followup_10.mail_template_id = mail_template
        self.create_invoice('2025-05-01')

        with freeze_time('2025-05-12'), self.mock_mail_gateway(mail_unlink_sent=False):
            options = {
                'followup_line': followup_10,
                'partner_id': self.partner_a.id,
            }
            self.partner_a.send_followup_email(options=options)
        self.assertMailMail(mail_cc, 'sent', author=self.env.user.partner_id)
