# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
from contextlib import contextmanager
from unittest import mock

from odoo import fields
from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import freeze_time, tagged
from odoo.tools import file_open

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
@freeze_time("2020-12-01 03:45:00")
class TestWiseDirectDeposit(AccountTestInvoicingCommon):

    @contextmanager
    def _with_mocked_wise_request(self, expected_communications):
        """Checks that we send the right requests and returns corresponding mocked responses. Heavily inspired by
        patch_session in l10n_ke_edi_oscu."""
        module = self.test_module
        self.maxDiff = None
        test_case = self
        json_module = json
        expected_communications = iter(expected_communications)

        def mocked_wise_request(self, method, endpoint, data=None, params=None):

            def replace_ignore(dict_to_replace):
                """ Replace `___ignore___` in the expected request JSONs by unittest.mock.ANY,
                    which is equal to everything. """
                for k, v in dict_to_replace.items():
                    if v == '___ignore___':
                        dict_to_replace[k] = mock.ANY
                return dict_to_replace

            expected_route, expected_request_filename, expected_response_filename = next(expected_communications)
            test_case.assertEqual(endpoint, expected_route)

            if method != 'GET':
                with file_open(f"{module}/tests/mocked_requests/{expected_request_filename}.json", "r") as request_file:
                    expected_request = json_module.loads(request_file.read(), object_hook=replace_ignore)
                    test_case.assertEqual(
                        data,
                        expected_request,
                        f"Expected request did not match actual request for route {endpoint}.",
                    )

            with file_open(f"{module}/tests/mocked_responses/{expected_response_filename}.json", "r") as response_file:
                return json_module.loads(response_file.read())

        with mock.patch(
            'odoo.addons.l10n_us_direct_deposit.models.wise_request.Wise._Wise__make_api_request', side_effect=mocked_wise_request, autospec=True,
        ):
            yield

        if next(expected_communications, None):
            self.fail("Not all expected calls were made!")

    @classmethod
    def collect_company_accounting_data(cls, company):
        res = super().collect_company_accounting_data(company)
        company.update({
            'wise_api_key': 'dummy_key',
            'wise_environment': 'sandbox',
            'wise_profile_identifier': '01234567',
        })

        return res

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.write({
            'email': 'partner_a@example.com',
        })
        cls.partner_b.write({
            'city': 'Tracy',
            'street': '7500 W Linne Road',
            'country_id': cls.env.ref('base.us').id,
            'state_id': cls.env.ref('base.state_us_5').id,
            'zip': '95304',
            'email': 'partner_b@example.com',
        })

        # This bank account will already appear in wise.
        cls.bank_partner_a = cls.env["res.partner.bank"].create({
            "partner_id": cls.partner_a.id,
            "acc_number": "987654321",
            "clearing_number": "123456789",
            "l10n_us_bank_account_type": "savings",
            "wise_account_type": "aba",
            "allow_out_payment": True,
        })

        # Write separately to ignore compute.
        cls.bank_partner_a.wise_bank_account = "1"

        # New bank account for partner_b
        cls.bank_partner_b = cls.env["res.partner.bank"].create({
            "partner_id": cls.partner_b.id,
            "allow_out_payment": True,
            "acc_number": "123456780",
            "clearing_number": "987654321",
            "wise_account_type": "fedwire_local",
        })

        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.payment_method = cls.env.ref('l10n_us_direct_deposit.account_payment_method_wise')
        cls.company_data['default_journal_bank'].available_payment_method_ids |= cls.payment_method
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id,
        }])

        cls.env.user.tz = "America/Los_Angeles"

        def create_payment(partner, amount):
            payment = cls.env['account.payment'].create({
                "partner_id": partner.id,
                "memo": "Test Memo",
                "amount": amount,
                "payment_type": "outbound",
                "payment_method_line_id": cls.payment_method_line.id,
                "date": fields.Date.context_today(cls.env.user),
            })
            payment.action_post()
            return payment

        cls.batch = cls.env["account.batch.payment"].create({
            "journal_id": cls.company_data["default_journal_bank"].id,
            "batch_type": "outbound",
        })

        payments = create_payment(cls.partner_b, 567.89) |\
                   create_payment(cls.partner_b, 456.78) |\
                   create_payment(cls.partner_a, 543.21) |\
                   create_payment(cls.partner_a, 123.45)
        # Sort to ensure we set the payments according to the _order. Otherwise, the tests won't be consistent.
        cls.batch.payment_ids = payments.sorted()

    def test_wise_batch_transfer(self):
        """Tests the entire flow of validating a batch payment to multiple vendors.
        In this test, partner_a is already established with Wise while partner_b needs to be created. The purpose of each
        API call is described next to them and they are split into logical groups."""
        with self._with_mocked_wise_request([
            ('/v3/profiles/01234567/batch-groups', 'create_batch_request', 'create_batch_response'),  # Create the batch
            ('/v2/accounts', '', 'get_accounts_response'),  # Get all accounts

            ('/v3/profiles/01234567/quotes', 'create_quote_request', 'create_quote_response'),  # Create a quote for partner_a
            ('/v3/profiles/01234567/batch-groups/1/transfers', 'create_transfer_request', 'create_transfer_response'),  # Create a transfer for partner_a

            ('/v3/profiles/01234567/quotes', 'create_quote_request', 'create_quote_response'),  # Create a quote for partner_a
            ('/v3/profiles/01234567/batch-groups/1/transfers', 'create_transfer_request', 'create_transfer_response'),  # Create a transfer for partner_a

            ('/v1/accounts', 'create_account_request', 'create_account_response'),  # Create partner_b's customer account

            ('/v3/profiles/01234567/quotes', 'create_quote_request', 'create_quote_response'),  # Create a quote for partner_b
            ('/v3/profiles/01234567/batch-groups/1/transfers', 'create_transfer_request', 'create_transfer_response'),  # Create a transfer for partner_b

            ('/v3/profiles/01234567/quotes', 'create_quote_request', 'create_quote_response'),  # create a quote for partner_b
            ('/v3/profiles/01234567/batch-groups/1/transfers', 'create_transfer_request', 'create_transfer_response'),  # create a transfer for partner_b

            ('/v3/profiles/01234567/batch-groups/1', '', 'get_batch_response'),  # Fetch latest batch data
            ('/v3/profiles/01234567/batch-groups/1', 'complete_batch_request', 'complete_batch_response'),  # create a transfer for partner_b
        ]):
            redirect_action = self.batch.validate_batch()
            self.assertEqual(redirect_action, {'type': 'ir.actions.act_url', 'url': 'https://sandbox.transferwise.tech/transactions/batch/1'})

    def test_wise_batch_validity_errors(self):
        """This implementation currently only supports USD currency, all others should be blocked."""
        first_payment = self.batch.payment_ids.sorted()[0]
        first_payment.currency_id = self.env.ref('base.MXN')
        with self.assertRaises(RedirectWarning) as ctx:
            self.batch.validate_batch()
        self.assertEqual(ctx.exception.args[0], "All payments in the batch must be in USD.\nNon-USD payments are not yet supported.")

        first_payment.date = "2020-12-03 03:45:00"
        validate_action = self.batch.validate_batch()
        validate_wizard = self.env['account.batch.error.wizard'].browse(validate_action['res_id'])
        error_lines = validate_wizard.error_line_ids
        warning_lines = validate_wizard.warning_line_ids

        self.assertEqual(len(error_lines), 1, msg="There should be 1 error line")
        self.assertEqual(len(warning_lines), 1, msg="There should be 1 warning line")

        self.assertEqual("All payments in the batch must be in USD.", error_lines.description)
        self.assertEqual("Non-USD payments are not yet supported.", error_lines.help_message)

        self.assertEqual("Wise will send the entire batch payment as soon as you fund it.", warning_lines.description)
        self.assertEqual("Scheduled payments are not yet supported.", warning_lines.help_message)

    def test_wise_api_errors(self):
        """The Wise API returns parsable json error messages to present to the user.
        This tests our capability to understand such messages and convert them to a UserError that makes sense."""
        with self._with_mocked_wise_request([
            ('/v3/profiles/01234567/batch-groups', 'create_batch_request', 'create_batch_response'),  # Create the batch
            ('/v2/accounts', '', 'get_accounts_response'),  # Get all accounts
            ('/v3/profiles/01234567/quotes', 'create_quote_request', 'create_quote_error_response'),  # Create a bad quote
        ]), self.assertRaises(UserError) as ctx:
            self.batch.validate_batch()
        self.assertEqual(ctx.exception.args[0], "Failed to create a quote on Wise:\n- sourceAmount: Please type in a number that's larger than 0.")
