# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, Command
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class OSSTaxReportTest(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.company.country_id = cls.env.ref('base.be')
        cls.env.company.account_fiscal_country_id = cls.env.ref('base.be')
        cls.env.company.vat = 'BE0477472701'
        cls.env.company.phone = '555-555-5555'
        cls.env.company.email = 'test@example.com'
        cls.env.company.currency_id = cls.env.ref('base.EUR')

        account_payable = cls.env['account.account'].create({
            'name': "VAT Payable: VAT Current Account (C/A)",
            'code': "4512",
            'account_type': 'liability_payable',
            'reconcile': True,
            'non_trade': True,
        })
        account_receivable = cls.env['account.account'].create({
            'name': "VAT Recoverable: VAT Current Account (C/A)",
            'code': "4112",
            'account_type': 'asset_receivable',
            'reconcile': True,
            'non_trade': True,
        })

        tax_group = cls.env['account.tax.group'].create({
            'name': 'tax_group',
            'country_id': cls.env.ref('base.be').id,
            'tax_payable_account_id': account_payable.id,
            'tax_receivable_account_id': account_receivable.id,
        })

        tax_21, tax_06 = cls.env['account.tax'].create([
            {
                'name': "tax_21",
                'amount_type': 'percent',
                'amount': 21.0,
                'country_id': cls.env.ref('base.be').id,
                'tax_group_id': tax_group.id,
            },
            {
                'name': "tax_06",
                'amount_type': 'percent',
                'amount': 6.0,
                'country_id': cls.env.ref('base.be').id,
                'tax_group_id': tax_group.id,
            },
        ])
        cls.tax_06 = tax_06
        cls.tax_21 = tax_21

        cls.env.company._map_eu_taxes()

        cls.product_1, cls.product_2 = cls.env['product.product'].create([
            {
                'name': 'product_1',
                'lst_price': 1000.0,
                'taxes_id': [Command.set(cls.tax_21.ids)],
            },
            {
                'name': 'product_2',
                'lst_price': 500.0,
                'taxes_id': [Command.set(cls.tax_06.ids)],
            },
        ])

        cls.partner_be = cls.env['res.partner'].create({
            'name': 'Partner BE',
            'country_id': cls.env.ref('base.be').id,
        })
        cls.partner_fr = cls.env['res.partner'].create({
            'name': 'Partner FR',
            'country_id': cls.env.ref('base.fr').id,
        })
        cls.partner_lu = cls.env['res.partner'].create({
            'name': 'Partner LU',
            'country_id': cls.env.ref('base.lu').id,
        })
        cls.partner_nl = cls.env['res.partner'].create({
            'name': 'Partner NL',
            'country_id': cls.env.ref('base.nl').id,
        })
        cls.partner_gr = cls.env['res.partner'].create({
            'name': 'Partner GR',
            'country_id': cls.env.ref('base.gr').id,
        })

        cls.init_invoice('out_invoice', partner=cls.partner_be, products=cls.product_1, invoice_date=fields.Date.from_string('2021-04-01'), post=True)
        cls.init_invoice('out_invoice', partner=cls.partner_fr, products=cls.product_1, invoice_date=fields.Date.from_string('2021-05-23'), post=True)
        cls.init_invoice('out_invoice', partner=cls.partner_lu, products=cls.product_1, invoice_date=fields.Date.from_string('2021-06-12'), post=True)
        cls.init_invoice('out_refund', partner=cls.partner_lu, products=cls.product_2, invoice_date=fields.Date.from_string('2021-06-15'), post=True)
        cls.init_invoice('out_invoice', partner=cls.partner_nl, products=cls.product_1, invoice_date=fields.Date.from_string('2021-05-09'), post=True)
        cls.init_invoice('out_refund', partner=cls.partner_nl, products=cls.product_1, invoice_date=fields.Date.from_string('2021-05-11'), post=True)
        cls.init_invoice('out_refund', partner=cls.partner_gr, products=cls.product_1, invoice_date=fields.Date.from_string('2021-06-26'), post=True)

    def _assert_closing_lines(self, entry, expected_lines_dict):
        for line, expected_line in zip(entry.line_ids, expected_lines_dict):
            for key in expected_line:
                self.assertEqual(line.mapped(key)[0], expected_line[key])

    def test_tax_report_oss(self):
        """ Test tax report's content for 'domestic' foreign VAT fiscal position option.
        """
        report = self.env.ref('l10n_eu_oss_reports.oss_sales_report')
        options = self._generate_options(report, fields.Date.from_string('2021-04-01'), fields.Date.from_string('2021-06-30'))

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                        Net               Tax
            [   0,                            1,                2],
            [
                ("Sales",                    '',               90),
                ("France",                   '',              200),
                ("20.0% FR VAT (20.0%)",   1000,              200),
                ("Total France",             '',              200),
                ("Greece",                   '',             -240),
                ("24.0% GR VAT (24.0%)",  -1000,             -240),
                ("Total Greece",             '',             -240),
                ("Luxembourg",               '',              130),
                ("17.0% LU VAT (17.0%)",   1000,              170),
                ("8.0% LU VAT (8.0%)",     -500,              -40),
                ("Total Luxembourg",         '',              130),
                ("Netherlands",              '',              0.0),
                ("21.0% NL VAT (21.0%)",    0.0,              0.0),
                ("Total Netherlands",        '',              0.0),
                ("Total Sales",              '',               90),
            ],
            options,
        )

    def test_tax_report_oss_closing(self):
        tax_return = self.env['account.return'].create({
            'name': "test return",
            'date_from': '2021-04-01',
            'date_to': '2021-06-30',
            'type_id': self.env.ref('l10n_eu_oss_reports.eu_oss_sales_tax_return_type').id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            tax_return.action_validate(bypass_failing_tests=True)

        self.assertEqual(len(tax_return.closing_move_ids), 1)

        self._assert_closing_lines(
            tax_return.closing_move_ids,
            [
                {'account_id.code':     '251002',        'debit': 200,       'credit': 0},
                {'account_id.code':     '251002',        'debit': 0,         'credit': 0},
                {'account_id.code':     '251002',        'debit': 0,         'credit': 240},
                {'account_id.code':     '251002',        'debit': 170,       'credit': 0},
                {'account_id.code':     '251002',        'debit': 0,         'credit': 40},
                {'account_id.code':     '252001',        'debit': 0,         'credit': 90},
            ]
        )

    def test_oss_import_report(self):
        self.product_1.account_tag_ids += self.env.ref('l10n_eu_oss.tag_eu_import')
        self.init_invoice('out_invoice', partner=self.partner_fr, products=self.product_1, invoice_date='2021-04-01', post=True)

        report = self.env.ref('l10n_eu_oss_reports.oss_imports_report')
        options = self._generate_options(report, '2021-04-01', '2021-06-30')

        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                        Net               Tax
            [   0,                            1,                2],
            [
                ("Sales",                    '',              200),
                ("France",                   '',              200),
                ("20.0% FR VAT (20.0%)",   1000,              200),
                ("Total France",             '',              200),
                ("Total Sales",              '',              200),
            ],
            options,
        )

    def test_generate_oss_xml_be(self):
        report = self.env.ref('l10n_eu_oss_reports.oss_sales_report')
        options = self._generate_options(report, fields.Date.from_string('2021-04-01'), fields.Date.from_string('2021-06-30'))

        expected_xml = """
            <ns0:OSSConsignment
              xmlns:ns2="urn:minfin.fgov.be:oss:common"
              xmlns:ns1="http://www.minfin.fgov.be/InputCommon"
              xmlns:ns0="http://www.minfin.fgov.be/OSSDeclaration"
              OSSDeclarationNbr="1">
              <ns0:OSSDeclaration SequenceNumber="1">
                <ns0:Trader_ID>
                  <ns2:VATNumber issuedBy="BE">0477472701</ns2:VATNumber>
                </ns0:Trader_ID>
                <ns0:Period>
                  <ns2:Year>2021</ns2:Year>
                  <ns2:Quarter>2</ns2:Quarter>
                </ns0:Period>
                <ns0:OSSDeclarationInfo SequenceNumber="1">
                  <ns2:MemberStateOfConsumption>FR</ns2:MemberStateOfConsumption>
                  <ns2:OSSDeclarationRows SequenceNumber="1">
                    <ns2:SupplyType>GOODS</ns2:SupplyType>
                    <ns2:VatRateType type="STANDARD">20.00</ns2:VatRateType>
                    <ns2:VatAmount currency="EUR">200.0</ns2:VatAmount>
                    <ns2:TaxableAmount currency="EUR">1000.0</ns2:TaxableAmount>
                  </ns2:OSSDeclarationRows>
                </ns0:OSSDeclarationInfo>
                <ns0:OSSDeclarationInfo SequenceNumber="2">
                  <ns2:MemberStateOfConsumption>EL</ns2:MemberStateOfConsumption>
                  <ns2:CorrectionsInfo>
                    <ns2:Period>
                      <ns2:Year>2021</ns2:Year>
                      <ns2:Quarter>1</ns2:Quarter>
                    </ns2:Period>
                    <ns2:TotalVATAmountCorrection currency="EUR">-240.0</ns2:TotalVATAmountCorrection>
                  </ns2:CorrectionsInfo>
                </ns0:OSSDeclarationInfo>
                <ns0:OSSDeclarationInfo SequenceNumber="3">
                  <ns2:MemberStateOfConsumption>LU</ns2:MemberStateOfConsumption>
                  <ns2:OSSDeclarationRows SequenceNumber="1">
                    <ns2:SupplyType>GOODS</ns2:SupplyType>
                    <ns2:VatRateType type="STANDARD">17.00</ns2:VatRateType>
                    <ns2:VatAmount currency="EUR">170.0</ns2:VatAmount>
                    <ns2:TaxableAmount currency="EUR">1000.0</ns2:TaxableAmount>
                  </ns2:OSSDeclarationRows>
                  <ns2:CorrectionsInfo>
                    <ns2:Period>
                      <ns2:Year>2021</ns2:Year>
                      <ns2:Quarter>2</ns2:Quarter>
                    </ns2:Period>
                    <ns2:TotalVATAmountCorrection currency="EUR">-40.0</ns2:TotalVATAmountCorrection>
                  </ns2:CorrectionsInfo>
                </ns0:OSSDeclarationInfo>
              </ns0:OSSDeclaration>
            </ns0:OSSConsignment>
        """

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    def test_tax_units(self):
        report = self.env.ref('l10n_eu_oss_reports.oss_sales_report')
        self.company_data_2['company'].currency_id = self.env.ref('base.EUR')
        tax_unit = self.env['account.tax.unit'].create({
            'name': 'BE Tax Unit',
            'country_id': self.env.ref('base.be').id,
            'main_company_id': self.env.company.id,
            'company_ids': [Command.set([self.company_data['company'].id, self.company_data_2['company'].id])],
            'vat': 'BE0477472701',
        })
        options = self._generate_options(report, '2021-04-01', '2021-06-30')
        self.assertEqual(options['tax_unit'], tax_unit.id)
        self.assertEqual(
            [company['id'] for company in options['companies']],
            [self.company_data['company'].id, self.company_data_2['company'].id]
        )


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestTaxReportOSSNoMapping(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].account_fiscal_country_id = cls.env.ref('base.be')
        cls.company_data['company'].vat = 'BE0477472701'

        cls.tax_report = cls.env['account.report'].create({
            'name': 'Fictive tax report',
            'country_id': cls.company_data['company'].account_fiscal_country_id.id,
            'root_report_id': cls.env.ref("account.generic_tax_report").id,
            'column_ids': [Command.create({'name': 'balance', 'sequence': 1, 'expression_label': 'balance',})],
        })
        cls.tax_return_type = cls.env['account.return.type'].create({
            'name': "Fictive Return Type",
            'report_id': cls.tax_report.id,
        })
        report_line_invoice_base_line = cls._create_tax_report_line('Invoice base', cls.tax_report, sequence=1, tag_name='-invoice_base_line')
        report_line_refund_base_line = cls._create_tax_report_line('Refund base', cls.tax_report, sequence=2, tag_name='refund_base_line')

        # Create an OSS tax from scratch
        cls.env['account.tax.group'].create({
            'name': 'tax_group',
            'country_id': cls.company_data['company'].account_fiscal_country_id.id,
            'tax_payable_account_id': cls.company_data['default_tax_account_payable'].id,
            'tax_receivable_account_id': cls.company_data['default_tax_account_receivable'].id,
        })
        oss_tag = cls.env.ref('l10n_eu_oss.tag_oss')
        oss_fp = cls.env['account.fiscal.position'].create({
            'name': 'OSS B2C Denmark',
            'country_id': cls.env.ref('base.dk').id,
            'company_id': cls.company_data['company'].id,
            'auto_apply': True,
        })
        cls.oss_tax = cls.env['account.tax'].create({
            'name': 'OSS tax for DK',
            'amount': 25,
            'country_id': cls.company_data['company'].account_fiscal_country_id.id,
            'fiscal_position_ids': [Command.link(oss_fp.id)],
            'invoice_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(report_line_invoice_base_line.expression_ids._get_matching_tags().ids + oss_tag.ids)],
                }),
                Command.create({
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set(oss_tag.ids)],
                }),
            ],
            'refund_repartition_line_ids': [
                Command.create({
                    'repartition_type': 'base',
                    'tag_ids': [Command.set(report_line_refund_base_line.expression_ids._get_matching_tags().ids + oss_tag.ids)],
                }),
                Command.create({
                    'repartition_type': 'tax',
                    'tag_ids': [Command.set(oss_tag.ids)],
                }),
            ],
        })


    def test_oss_tax_report_mixed_tags(self):
        """Checks that the tax report correctly takes into account the amount of the account move lines wearing tax tag
        when it is also wearing an OSS tag.
        """
        self.init_invoice(
            move_type='out_invoice',
            partner=self.partner_a,
            invoice_date=fields.Date.from_string('2022-02-01'),
            amounts=[100.0],
            taxes=[self.oss_tax],
            post=True,
        )
        options = self._generate_options(
            self.tax_report,
            fields.Date.from_string('2022-02-01'),
            fields.Date.from_string('2022-02-28'),
        )
        report_results = self.tax_report._get_lines(options)

        self.assertLinesValues(
            # pylint: disable=C0326
            report_results,
            #   Name             Balance
            [   0,                    1],
            [
                ('Invoice base', 100.00),
                ('Refund base',    0.00),
            ],
            options,
        )

    def test_closing_entry(self):
        """Check the closing entry doesn't take the account move line wearing the OSS tag into account"""
        self.init_invoice(
            move_type='out_invoice',
            partner=self.partner_a,
            invoice_date=fields.Date.from_string('2022-02-01'),
            amounts=[100.0],
            taxes=[self.oss_tax],
            post=True,
        )
        options = self._generate_options(
            self.tax_report,
            fields.Date.from_string('2022-02-01'),
            fields.Date.from_string('2022-02-28'),
        )

        oss_return = self.env['account.return'].create({
            'name': "OSS return",
            'date_from': '2022-02-01',
            'date_to': '2022-02-28',
            'type_id': self.tax_return_type.id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            oss_return.action_validate(bypass_failing_tests=True)

        tax_closing_entry_lines = oss_return.closing_move_ids.line_ids.filtered(lambda l: l.balance != 0.0)

        self.assertEqual(len(tax_closing_entry_lines), 0, "The tax closing entry shouldn't take amls wearing the OSS tag into account")

    def test_tax_report_oss(self):
        """ Test tax report's content for 'domestic' foreign VAT fiscal position option."""
        self.init_invoice(
            move_type='out_invoice',
            partner=self.partner_a,
            invoice_date=fields.Date.from_string('2022-02-01'),
            amounts=[100.0],
            taxes=[self.oss_tax],
            post=True,
        )
        report = self.env.ref('l10n_eu_oss_reports.oss_sales_report')
        options = self._generate_options(report, '2022-02-01', '2022-02-28')
        self.assertLinesValues(
            # pylint: disable=C0326
            report._get_lines(options),
            #   Name                          Net               Tax
            [   0,                              1,                2],
            [
                ("Sales",                      '',             25.0),
                ("Denmark",                    '',             25.0),
                ("OSS tax for DK (25.0%)",  100.0,             25.0),
                ("Total Denmark",              '',             25.0),
                ("Total Sales",                '',             25.0),
            ],
            options,
        )

    def test_oss_variants_available(self):
        # Ensure OSS variants are available from their root reports (using OSS availability condition)
        generic_tax_report = self.env.ref('account.generic_tax_report')
        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        oss_reports = {
            self.env.ref('l10n_eu_oss_reports.oss_sales_report').id,
            self.env.ref('l10n_eu_oss_reports.oss_imports_report').id,
        }
        available_oss = [v for v in options['available_variants'] if v['id'] in oss_reports]
        self.assertEqual(
            len(available_oss), 2,
            "OSS variants should be available in the generic tax report's variants"
        )

        # Remove OSS taxes
        oss_tag = self.env.ref('l10n_eu_oss.tag_oss')
        company_ids = generic_tax_report.get_report_company_ids(options)
        oss_repartition_lines = self.env['account.tax.repartition.line'].search([('tag_ids', 'in', oss_tag.ids), ('company_id', 'in', company_ids)])
        oss_repartition_lines.tax_id.unlink()

        options = self._generate_options(generic_tax_report, '2022-02-01', '2022-02-28')
        available_oss = [v for v in options['available_variants'] if v['id'] in oss_reports]
        self.assertEqual(
            len(available_oss), 0,
            "OSS variants should not be available in the generic tax report's variants because no OSS taxes could be found"
        )
