# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from contextlib import ExitStack, contextmanager, nullcontext
from unittest import SkipTest, mock
from unittest.mock import patch

from odoo import modules
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, freeze_time, tagged
from odoo.tools import file_open

from .mocked_invoice_response import generate_response
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_br_avatax.models.account_external_tax_mixin import (
    AccountExternalTaxMixin,
)

_logger = logging.getLogger(__name__)

DUMMY_SANDBOX_ID = "DUMMY_ID"
DUMMY_SANDBOX_KEY = "DUMMY_KEY"
TEST_DATETIME = "2025-02-05T22:55:17+00:00"


class TestBRMockedRequests(TransactionCase):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        # Any additional patches that need to be applied for the tests can be added here.
        self.mocked_l10n_br_iap_patches = []

    @contextmanager
    def _with_mocked_l10n_br_iap_request(self, expected_communications):
        """Checks that we send the right requests and returns corresponding mocked responses. Heavily inspired by
        patch_session in l10n_ke_edi_oscu."""
        module = self.test_module
        self.maxDiff = None
        test_case = self
        json_module = json
        expected_communications = iter(expected_communications)

        def mocked_l10n_br_iap_request(self, route, company, json=None):
            edi_installed = self.env['ir.module.module']._get('l10n_br_edi').state == 'installed'

            def replace_ignore(dict_to_replace):
                """Replace `___ignore___` in the expected request JSONs by unittest.mock.ANY,
                which is equal to everything. In addition, itemCode is always added to all tax
                requests if l10n_br_edi is installed. This means that a test case could pass with
                a specific file if only l10n_br_avatax is installed but fail if l10n_br_edi
                is also installed (or vise versa). As such, we skip it if edi is not installed that
                way we don't need to duplicate input files."""
                new_dict = {}
                for k, v in dict_to_replace.items():
                    if k == 'itemCode' and not edi_installed:
                        continue
                    if v == "___ignore___":
                        v = mock.ANY
                    new_dict[k] = v
                return new_dict

            expected_route, expected_request_filename, expected_response_filename = next(expected_communications)
            test_case.assertEqual(route, expected_route)
            with file_open(f"{module}/tests/mocked_requests/{expected_request_filename}.json", "r") as request_file:
                expected_request = json_module.loads(request_file.read(), object_hook=replace_ignore)
                test_case.assertEqual(
                    json,
                    expected_request,
                    f"Expected request did not match actual request for route {route}.",
                )

            with file_open(f"{module}/tests/mocked_responses/{expected_response_filename}.json", "r") as response_file:
                api_response = json_module.loads(response_file.read())

                if expected_route == "calculate_tax":
                    expected_lines = api_response["lines"]

                    # Generically get line information for any record type that supports the
                    # account.external.tax.mixin.
                    record_model, record_id = json['header']['documentCode'].split('_')
                    record = self.env[record_model].browse(int(record_id))
                    lines = [
                        line['base_line']['record']
                        for line in record._get_line_data_for_external_taxes()
                    ]

                    test_case.assertEqual(
                        len(lines), len(expected_lines), f"The sent record was expected to have {len(expected_lines)} lines.",
                    )

                    # Set the line IDs in the mocked response to the line IDs of this records.
                    for i, line in enumerate(expected_lines):
                        line["lineCode"] = lines[i].id

                return api_response

        with ExitStack() as patch_stack:
            patch_stack.enter_context(patch(
                f"{AccountExternalTaxMixin.__module__}.AccountExternalTaxMixin._l10n_br_iap_request",
                autospec=True,
                side_effect=mocked_l10n_br_iap_request,
            ))
            # Apply all other patches in addition to the required ones.
            for other_patch in self.mocked_l10n_br_iap_patches:
                patch_stack.enter_context(other_patch)
            yield

        if next(expected_communications, None):
            self.fail("Not all expected calls were made!")


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrCommon(AccountTestInvoicingCommon, TestBRMockedRequests):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(cls):
        res = super().setUpClass()
        cls._setup_credentials()
        cls.foreign_currency = cls.setup_other_currency('EUR')
        cls.fp_avatax = cls.env['account.fiscal.position'].create({
            'name': 'Avatax Brazil',
            'l10n_br_is_avatax': True,
        })

        cls._setup_partners()

        # Ensure the IAP service exists for this company. Otherwise, iap.account's get() method will fail.
        iap_service = cls.env.ref('l10n_br_avatax.iap_service_br_avatax')
        cls.env['iap.account'].create(
            {
                'service_id': iap_service.id,
                'company_ids': [(6, 0, cls.company_data['company'].ids)],
            }
        )

        cls._setup_products()

        return res

    @classmethod
    def _setup_credentials(cls):
        # Set real credentials here to run the integration tests
        cls.env.company.l10n_br_avatax_api_identifier = DUMMY_SANDBOX_ID
        cls.env.company.l10n_br_avatax_api_key = DUMMY_SANDBOX_KEY
        cls.env.company.l10n_br_avalara_environment = 'sandbox'

    @classmethod
    def _setup_partners(cls):
        company = cls.company_data['company']
        company.write({
            'street': 'Rua Marechal Deodoro 630',
            'street2': 'Edificio Centro Comercial Itália 24o Andar',
            'city': 'Curitiba',
            'state_id': cls.env.ref('base.state_br_pr').id,
            'country_id': cls.env.ref('base.br').id,
            'zip': '80010-010',
        })
        company.partner_id.l10n_br_tax_regime = 'individual'

        cls.partner = cls.env['res.partner'].create({
            'name': 'Avatax Brazil Test Partner',
            'street': 'Avenida SAP, 188',
            'street2': 'Cristo Rei',
            'city': 'São Leopoldo',
            'state_id': cls.env.ref('base.state_br_rs').id,
            'country_id': cls.env.ref('base.br').id,
            'zip': '93022-718',
            'property_account_position_id': cls.fp_avatax.id,
            'l10n_br_tax_regime': 'individual',
        })

        cls.partner_shipping_id = cls.env['res.partner'].create({
            'type': 'delivery',
            'street_name': 'Avenida Europa',
            'street_number': '2048',
            'street2': 'Jardim São Domingos',
            'state_id': cls.env.ref('base.state_br_sp').id,
            'city_id': cls.env.ref('l10n_br.city_br_124').id,
            'country_id': cls.env.ref('base.br').id,
            'city': 'Americana',
        })

    @classmethod
    def _setup_products(cls):
        common = {
            'l10n_br_ncm_code_id': cls.env.ref('l10n_br_avatax.49011000').id,
            'l10n_br_source_origin': '0',
            'l10n_br_sped_type': 'FOR PRODUCT',
            'l10n_br_use_type': 'use or consumption',
            'supplier_taxes_id': None,
        }

        cls.product = cls.env['product.product'].create({
            'name': 'Product',
            'default_code': 'PROD1',
            'barcode': '123456789',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })
        cls.product_user = cls.env['product.product'].create({
            'name': 'Odoo User',
            'list_price': 35.00,
            'standard_price': 35.00,
            **common,
        })
        cls.product_user_discount = cls.env['product.product'].create({
            'name': 'Odoo User Initial Discount',
            'list_price': -5.00,
            'standard_price': -5.00,
            **common,
        })
        cls.product_accounting = cls.env['product.product'].create({
            'name': 'Accounting',
            'list_price': 30.00,
            'standard_price': 30.00,
            **common,
        })
        cls.product_expenses = cls.env['product.product'].create({
            'name': 'Expenses',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })
        cls.product_invoicing = cls.env['product.product'].create({
            'name': 'Invoicing',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })

    @classmethod
    @contextmanager
    def _skip_no_credentials(cls):
        company = cls.env.company
        if company.l10n_br_avatax_api_identifier == DUMMY_SANDBOX_ID or \
           company.l10n_br_avatax_api_key == DUMMY_SANDBOX_KEY or \
           company.l10n_br_avalara_environment != 'sandbox':
            raise SkipTest('no Avalara credentials')
        yield

    @classmethod
    @contextmanager
    def _capture_request_br(cls, return_value=None):
        with patch(f'{AccountExternalTaxMixin.__module__}.AccountExternalTaxMixin._l10n_br_iap_request', return_value=return_value) as mocked:
            yield mocked

    @classmethod
    def _create_invoice_01_and_expected_response(cls, move_type='out_invoice'):
        products = (
            cls.product_user,
            cls.product_accounting,
            cls.product_expenses,
            cls.product_invoicing,
        )
        invoice = cls.env['account.move'].create({
            'move_type': move_type,
            'partner_id': cls.partner.id,
            'fiscal_position_id': cls.fp_avatax.id,
            'invoice_date': '2021-01-01',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product.id,
                    'tax_ids': None,
                    'price_unit': product.list_price,
                }) for product in products
            ],
        })
        invoice.invoice_line_ids[0].discount = 10

        return invoice, generate_response(invoice.invoice_line_ids)

    @classmethod
    def _create_invoice_02(cls, operation_types=False):
        products = (
            cls.product_user,
            cls.product_accounting,
            cls.product_expenses,
            cls.product_invoicing,
        )

        operation_types = operation_types or (
            cls.env.ref('l10n_br_avatax.operation_type_1'),
            cls.env.ref('l10n_br_avatax.operation_type_2'),
            cls.env.ref('l10n_br_avatax.operation_type_3'),
            cls.env.ref('l10n_br_avatax.operation_type_60'),
        )
        invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'fiscal_position_id': cls.fp_avatax.id,
            'invoice_date': '2021-01-01',
            'invoice_line_ids': [
                Command.create({
                    'product_id': product.id,
                    'tax_ids': None,
                    'price_unit': product.list_price,
                    'l10n_br_goods_operation_type_id': operation_type and operation_type.id,
                }) for product, operation_type in zip(products, operation_types)
            ],
        })

        return invoice

    @classmethod
    def _create_invoice_with_diff_partner_shipping(cls):
        invoice = cls._create_invoice_02(operation_types=(False, ) * 4)
        # Create a delivery address for partner
        partner_shipping_id = cls.partner_shipping_id
        invoice.partner_id.write({
            'child_ids': (4, partner_shipping_id.id),
            'l10n_br_tax_regime': 'realProfit',
            'city_id': cls.env.ref("l10n_br.city_br_002"),
        })
        # Default document type is NF-e
        invoice.write({
            'invoice_date': TEST_DATETIME,
            'l10n_latam_document_type_id': cls.env.ref('l10n_br.dt_55').id,
            'l10n_br_cnae_code_id': cls.env.ref("l10n_br_avatax.cnae_6209100").id,
            'partner_shipping_id': partner_shipping_id.id
        })
        return invoice


class TestAvalaraBrInvoiceCommon(TestAvalaraBrCommon):
    def assertInvoice(self, invoice, test_exact_response):
        self.assertEqual(
            len(invoice.invoice_line_ids.tax_ids),
            0,
            'There should be no tax rate on the line.'
        )

        self.assertRecordValues(invoice, [{
            'amount_total': 91.50,
            'amount_untaxed': 91.50,
            'amount_tax': 0.0,
        }])

        # When the external tests run this will need to do an IAP request which isn't possible in testing mode, see:
        # 7416acc111793ac1f7fd0dc653bb05cf7af28ebe
        with patch.object(modules.module, 'current_test', False) if 'external_l10n' in self.test_tags else nullcontext():
            invoice.action_post()

        if test_exact_response:
            expected_amounts = {
                'amount_total': 91.50,
                'amount_untaxed': 91.50 - 10.98 - 5.02,
                'amount_tax': 10.98 + 5.02,
            }
            self.assertRecordValues(invoice, [expected_amounts])

            self.assertEqual(invoice.tax_totals['total_amount_currency'], expected_amounts['amount_total'])
            self.assertEqual(invoice.tax_totals['base_amount_currency'], expected_amounts['amount_untaxed'])

            self.assertEqual(len(invoice.tax_totals['subtotals']), 1)
            self.assertEqual(invoice.tax_totals['subtotals'][0]['base_amount_currency'], expected_amounts['amount_untaxed'])

            avatax_mapping = {avatax_line['lineCode']: avatax_line for avatax_line in test_exact_response['lines']}
            for line in invoice.invoice_line_ids:
                avatax_line = avatax_mapping[line.id]
                self.assertEqual(
                    line.price_total,
                    avatax_line['lineAmount'] - avatax_line['lineTaxedDiscount'],
                    f"Tax-included price doesn't match tax returned by Avatax for line {line.id} (product: {line.product_id.display_name})."
                )
                self.assertAlmostEqual(
                    line.price_subtotal,
                    avatax_line['lineNetFigure'] - avatax_line['lineTaxedDiscount'],
                    msg=f'Wrong Avatax amount for {line.id} (product: {line.product_id.display_name}), there is probably a mismatch between the test SO and the mocked response.'
                )

        else:
            for line in invoice.invoice_line_ids:
                product_name = line.product_id.display_name
                self.assertGreater(len(line.tax_ids), 0, 'Line with %s did not get any taxes set.' % product_name)

            self.assertGreater(invoice.amount_tax, 0.0, 'Invoice has a tax_amount of 0.0.')


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrInvoice(TestAvalaraBrInvoiceCommon):
    def test_01_invoice_br(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request_br(return_value=response):
            self.assertInvoice(invoice, test_exact_response=response)

    def test_02_non_brl(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.currency_id = self.env.ref('base.USD')

        with self.assertRaisesRegex(UserError, r'.* Brazilian Real is required to calculate taxes with Avatax.'):
            self.assertInvoice(invoice, test_exact_response=None)

    def test_03_transport_cost(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        transport_cost_products = self.env['product.product'].create([{
            'name': 'freight',
            'list_price': 10.00,
            'l10n_br_transport_cost_type': 'freight',
        }, {
            'name': 'insurance',
            'list_price': 20.00,
            'l10n_br_transport_cost_type': 'insurance',
        }, {
            'name': 'other',
            'list_price': 30.00,
            'l10n_br_transport_cost_type': 'other',
        }])

        for product in transport_cost_products:
            self.env['account.move.line'].create({
                'product_id': product.id,
                'price_unit': product.list_price,
                'move_id': invoice.id,
            })

        # (line amount, freight, insurance, other) per line
        expecteds = [
            (35.00, 3.68, 7.37, 11.05),
            (30.00, 3.16, 6.32, 9.47),
            (15.00, 1.58, 3.16, 4.74),
            (15.00, 1.58, 3.15, 4.74), # note that the insurance amount is different from the line above to ensure the total adds up to 20
        ]

        api_request = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        actual_lines = api_request['lines']
        self.assertEqual(len(expecteds), len(actual_lines), 'Different amount of expected and actual lines.')

        for expected, line in zip(expecteds, actual_lines):
            amount, freight, insurance, other = expected
            self.assertEqual(amount, line['lineAmount'])
            self.assertEqual(freight, line['freightAmount'])
            self.assertEqual(insurance, line['insuranceAmount'])
            self.assertEqual(other, line['otherCostAmount'])

    def test_04_negative_line(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        self.env['account.move.line'].create({
            'product_id': self.product_user_discount.id,
            'move_id': invoice.id,
            'price_unit': -1_000.00,
        })

        with self._capture_request_br(), \
             self.assertRaisesRegex(UserError, "Avatax Brazil doesn't support negative lines."):
            invoice.action_post()

    def test_05_credit_note(self):
        """Tax calculation without setting operation types on the lines. This should use the default
            from the parent model instead. (salesReturn)
        """
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request_br(return_value=response):
            invoice.action_post()

        credit_note_wizard = self.env['account.move.reversal'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': invoice.journal_id.id,
        })
        credit_note_wizard.reverse_moves()

        credit_note = self.env['account.move'].search([('reversed_entry_id', '=', invoice.id)])
        self.assertTrue(credit_note, "A credit note should have been created.")

        payload = credit_note._prepare_l10n_br_avatax_document_service_call(credit_note._get_l10n_br_avatax_service_params())
        self.assertTrue(all(line['operationType'] == 'salesReturn' for line in payload['lines']), 'The default operationType for credit notes should be salesReturn.')
        self.assertEqual(payload['header']['invoicesRefs'][0]['documentCode'], f'account.move_{invoice.id}', 'The credit note should reference the original invoice.')

    def test_06_unique_operation_types(self):
        """Tax calculation with unique operation types on each line."""
        invoice = self._create_invoice_02()
        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        operation_types = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'complementary', 'amountComplementary', 'salesReturn']
        self.assertEqual(operation_types, expected_operation_types, 'The expected operation types are not properly set. It should be unique per line.')

    def test_07_override_operation_type(self):
        """Tax calculation with operation types set only on a single line. The rest should default to standardSales."""
        operation_types = (
            False,
            self.env.ref('l10n_br_avatax.operation_type_2'),
            False,
            False,
        )

        invoice = self._create_invoice_02(operation_types=operation_types)
        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        operation_types = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'complementary', 'standardSales', 'standardSales']
        self.assertEqual(operation_types, expected_operation_types, 'The expected operation types are not properly set.')

    def test_08_vendor_bill(self):
        """ Verify the differences between sending an invoice and a bill. """
        bill, response = self._create_invoice_01_and_expected_response(move_type='in_invoice')
        bill.l10n_latam_document_number = '1'
        self.assertEqual(
            bill.l10n_br_goods_operation_type_id,
            self.env.ref('l10n_br_avatax.operation_type_59'),
            "Default operation type for bills should be standardPurchase."
        )

        with self._capture_request_br(return_value=response) as patched:
            bill.action_post()

        payload = patched.call_args.args[2]
        self.assertEqual(
            payload['header']['operationType'],
            'standardPurchase',
            'The operationType for vendor bills should be standardPurchase.'
        )

    def test_09_ex_citation_in_payload(self):
        """ Ensure that the 'ex' citation from the NCM code is included in the Avatax API payload. """
        self.env.ref('l10n_br_avatax.49011000').write({'ex': '001'})
        invoice, _ = self._create_invoice_01_and_expected_response()
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        line = payload['lines'][0]
        self.assertEqual(line['itemDescriptor']['ex'], '001', "EX field should match the value set in NCM code")

    def test_10_tax_calculation_api_error(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        response = {
            "error": {
                "code": "TC000",
                "message": "Errors: ",
                "innerError": [
                    {
                        "code": "TC001",
                        "message": "Cannot find TaxCitation based on NCM for PIS",
                        "lineCode": invoice.invoice_line_ids.ids[0],
                        "where": {
                            "type": "PIS",
                            "hsCodes.codeType": "NCM",
                            "hsCodes.code": "49011000",
                            "date": "2025-07-18T00:00:00.000Z",
                        },
                        "lineIndex": 0,
                        "itemCode": "false",
                    },
                ],
            }
        }

        with self._capture_request_br(return_value=response), \
             self.assertRaisesRegex(UserError, "Cannot find TaxCitation based on NCM for PIS"):
            invoice.button_external_tax_calculation()

    @freeze_time(TEST_DATETIME)
    def test_11_service_invoice(self):
        """ Make sure that service invoices are handled correctly and can have CNAE overriden. """
        rio_city = self.env.ref("l10n_br.city_br_002")
        invoice = self._create_invoice_02(operation_types=(False, ) * 4)
        invoice.invoice_line_ids.mapped('product_id').write(
            {
                "type": "service",
                "l10n_br_property_service_code_origin_id": self.env["l10n_br.service.code"].create(
                    {"code": "12345", "city_id": rio_city.id},
                ),
            },
        )

        invoice.write({
            'invoice_date': TEST_DATETIME,
            'l10n_latam_document_type_id': self.env.ref('l10n_br.dt_SE').id,
            'l10n_br_cnae_code_id': self.env.ref("l10n_br_avatax.cnae_6209100").id,
        })
        invoice.partner_id.city_id = rio_city

        ncm_code_id = self.env.ref('l10n_br_avatax.49021000')
        ncm_code_id.l10n_br_cnae_code_id = self.env.ref('l10n_br_avatax.cnae_6204000')
        invoice.invoice_line_ids[-1].product_id.l10n_br_ncm_code_id = ncm_code_id

        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
        ]):
            invoice.action_post()

        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

    def test_12_service_invoice_with_installments(self):
        """Test that service invoices with installments clear tax_ids when using Avalara. It's necessary because Avalara
        expects installments to be sent without taxes for service invoices."""
        invoice, response = self._create_invoice_01_and_expected_response()
        rio_city = self.env.ref("l10n_br.city_br_002")

        invoice.invoice_payment_term_id = self.pay_terms_b.id
        invoice.l10n_latam_document_type_id = self.env.ref("l10n_br.dt_SE").id
        invoice.partner_id.city_id = rio_city

        # Mark all products as services and assign service code
        for line in invoice.invoice_line_ids:
            line.tax_ids = self.tax_sale_a
            line.product_id.write({
                'type': 'service',
                'l10n_br_property_service_code_origin_id': self.env['l10n_br.service.code'].create({
                    'code': '12345',
                    'city_id': rio_city.id,
                }),
            })

        # Ensure there's a tax amount
        self.assertGreater(invoice.amount_tax, 0, "There should be a tax amount on this invoice.")

        with self._capture_request_br(return_value=response) as captured:
            invoice._get_external_taxes()

        expected_untaxed_terms = invoice.invoice_payment_term_id._compute_terms(
            invoice.date,
            invoice.currency_id,
            invoice.company_id,
            tax_amount=0,
            tax_amount_currency=0,
            sign=1,
            untaxed_amount=invoice.amount_untaxed,
            untaxed_amount_currency=invoice.amount_untaxed,
        )

        self.assertEqual(
            [installment['grossValue'] for installment in captured.call_args[0][2]['header']['payment']['installment']],
            [term['company_amount'] for term in expected_untaxed_terms['line_ids']],
            "Installments should be sent without taxes."
        )

    def test_11_service_invoice_with_discount(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        invoice.invoice_line_ids.product_id.type = 'service'
        invoice.l10n_latam_document_type_id = self.env.ref('l10n_br.dt_SE')
        invoice.partner_id.city_id = self.env.ref('l10n_br.city_br_001')

        with self._capture_request_br(return_value=response):
            invoice.action_post()

        self.assertEqual(
            invoice.invoice_line_ids[0].price_total,
            35.0,
            "The discount shouldn't have been subtracted, it's already accounted for in lineNetFigure."
        )

    def test_13_service_invoice_with_rendered_address(self):
        rio_city = self.env.ref("l10n_br.city_br_002")
        ncm_code_id = self.env.ref('l10n_br_avatax.service_1_07')
        # Make a service invoice
        invoice = self._create_invoice_with_diff_partner_shipping()
        invoice.l10n_latam_document_type_id = self.env.ref('l10n_br.dt_SE').id
        # Configure the product to be a service type for rendered address
        invoice.invoice_line_ids.mapped('product_id').write(
            {
                "type": "service",
                "l10n_br_property_service_code_origin_id": self.env["l10n_br.service.code"].create(
                    {"code": "1.07", "city_id": rio_city.id},
                ),
                "l10n_br_ncm_code_id": ncm_code_id,
            },
        )

        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "nfse_rendered_address_request", "nfse_rendered_address_response"),
        ]):
            invoice.action_post()

    def test_14_goods_invoice_with_delivery_address(self):
        invoice = self._create_invoice_with_diff_partner_shipping()
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        delivery = payload['header']['locations'].get('delivery')
        self.assertTrue(delivery, "Delivery address should be sent in request when partner_shipping_id is not the same as partner_id")


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrSettings(TestAvalaraBrInvoiceCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['res.config.settings'].create({})
        cls.settings.l10n_br_avatax_portal_email = "test@example.com"
        cls.settings.company_id.vat = "00.623.904/0001-73"

    def test_01_create_account_success(self):
        return_value = {
            'avalara_api_id': 'API_ID',
            'avalara_api_key': 'API_KEY',
        }
        with self._capture_request_br(return_value=return_value):
            self.settings.create_account()

        self.assertRecordValues(self.env.company, [{
            'l10n_br_avatax_api_identifier': 'API_ID',
            'l10n_br_avatax_api_key': 'API_KEY',
        }])

    def test_02_create_account_error_type_1(self):
        return_value = {
            'message': 'One or more errors occurred. (CEP \'32516-076\' not found)',
            'isError': True,
        }
        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, r'One or more errors occurred. \(CEP \'32516-076\' not found\)'):
            self.settings.create_account()

        return_value = {
            'message': 'An unhandled error occurred. Trace ID: xxx',
            'isError': True
        }
        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, 'Please ensure the address on your company is correct'):
            self.settings.create_account()

    def test_03_create_account_error_type_2(self):
        return_value = {
            'message': '{"errors":{"Login do usuário master":["Login já utlizado"]},"title":"One or more validation errors occurred.","status":400,"traceId":"0HMPVCEB27KLU:000000E5"}',
            'isError': True,
        }

        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, 'Login já utlizado'):
            self.settings.create_account()

    def test_04_no_false(self):
        """ Do not send "false" to the API for empty fields. It will populate "false" in some of the fields on Avatax's side
        and cause issues during EDI. """
        with self._capture_request_br(return_value={}) as mocked_request:
            self.settings.create_account()

        for k, v in mocked_request.call_args[0][2].items():
            self.assertNotEqual(v, False, f"{k} was False instead of empty string")

    def test_05_formatted_vat(self):
        """ Properly format the VAT numbers to CNPJ even in compact form."""
        with self._capture_request_br(return_value={}) as mocked_request:
            self.settings.create_account()

        arguments = mocked_request.call_args[0][2]
        self.assertEqual(self.settings.company_id.vat, '00623904000173', 'CNPJ should be compacted in internal storage')
        self.assertEqual(arguments['cnpj'], '00.623.904/0001-73', 'CNPJ must be formatted for account creation')


@tagged('external_l10n', 'external', '-at_install', 'post_install', '-standard')
class TestAvalaraBrInvoiceIntegration(TestAvalaraBrInvoiceCommon):
    def test_01_invoice_integration_br(self):
        with self._skip_no_credentials():
            invoice, _ = self._create_invoice_01_and_expected_response()
            self.assertInvoice(invoice, test_exact_response=False)
