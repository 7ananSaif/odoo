# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon
from odoo.tests import tagged
from freezegun import freeze_time
from unittest.mock import patch


@tagged('post_install_l10n', 'post_install', '-at_install')
class BelgiumTaxReportTest(AccountSalesReportCommon):

    @classmethod
    @AccountSalesReportCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company.update({
            'vat': 'BE0477472701',
        })

    @freeze_time('2019-12-31')
    def test_generate_xml_minimal(self):
        company = self.env.company
        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        ref = str(company.partner_id.id) + '112019'

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>11</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Data>
                    <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-31')
    def test_generate_xml_minimal_with_comment(self):
        company = self.env.company
        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})
        options['comment'] = "foo"

        ref = str(company.partner_id.id) + '112019'

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
               <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
                   <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                       <ns2:Declarant>
                           <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                           <Name>company_1_data</Name>
                           <Street></Street>
                           <PostCode></PostCode>
                           <City></City>
                           <CountryCode>BE</CountryCode>
                           <EmailAddress>jsmith@mail.com</EmailAddress>
                           <Phone>+32475123456</Phone>
                       </ns2:Declarant>
                       <ns2:Period>
                           <ns2:Month>11</ns2:Month>
                           <ns2:Year>2019</ns2:Year>
                       </ns2:Period>
                       <ns2:Data>
                           <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                       </ns2:Data>
                       <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                       <ns2:Ask Restitution="NO"/>
                       <ns2:Comment>foo</ns2:Comment>
                   </ns2:VATDeclaration>
               </ns2:VATConsignment>
               """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(
                self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-31')
    def test_generate_xml_minimal_with_representative(self):
        company = self.env.company
        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})

        # Create a new partner for the representative and link it to the company.
        representative = self.env['res.partner'].create({
            'company_type': 'company',
            'name': 'Fidu BE',
            'street': 'Fidu Street 123',
            'city': 'Brussels',
            'zip': '1000',
            'country_id': self.env.ref('base.be').id,
            'vat': 'BE0477472701',
            'phone': '+32470123456',
            'email': 'info@fidu.be',
        })
        company.account_representative_id = representative.id

        # The partner_id is changing between execution of the test so we need to append it manually to the reference.
        ref = str(company.partner_id.id) + '112019'

        # This is the minimum expected from the belgian tax report XML.
        # Only the representative node has been added to make sure it appears in the XML.
        expected_xml = """
            <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
                <ns2:Representative>
                    <RepresentativeID identificationType="NVAT" issuedBy="BE">0477472701</RepresentativeID>
                    <Name>Fidu BE</Name>
                    <Street>Fidu Street 123</Street>
                    <PostCode>1000</PostCode>
                    <City>Brussels</City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>info@fidu.be</EmailAddress>
                    <Phone>+32470123456</Phone>
                </ns2:Representative>
                <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                    <ns2:Declarant>
                        <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                        <Name>company_1_data</Name>
                        <Street></Street>
                        <PostCode></PostCode>
                        <City></City>
                        <CountryCode>BE</CountryCode>
                        <EmailAddress>jsmith@mail.com</EmailAddress>
                        <Phone>+32475123456</Phone>
                    </ns2:Declarant>
                    <ns2:Period>
                        <ns2:Month>11</ns2:Month>
                        <ns2:Year>2019</ns2:Year>
                    </ns2:Period>
                    <ns2:Data>
                        <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                    </ns2:Data>
                    <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                    <ns2:Ask Restitution="NO"/>
                </ns2:VATDeclaration>
            </ns2:VATConsignment>
            """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-31')
    def test_generate_xml(self):
        company = self.env.company
        first_tax = self.env['account.tax'].search([('name', '=', '21% M'), ('company_id', '=', self.company_data['company'].id)], limit=1)
        second_tax = self.env['account.tax'].search([('name', '=', '21% M.Cocont'), ('company_id', '=', self.company_data['company'].id)], limit=1)

        # Create and post a move with two move lines to get some data in the report
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'partner_id': self.partner_a.id,
            'invoice_date': '2019-11-12',
            'date': '2019-11-12',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test 1',
                'price_unit': 100,
                'tax_ids': first_tax.ids,
            }), (0, 0, {
                'product_id': self.product_b.id,
                'quantity': 1.0,
                'name': 'product test 2',
                'price_unit': 50,
                'tax_ids': second_tax.ids,
            })]
        })
        move.action_post()

        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        ref = str(company.partner_id.id) + '112019'

        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">

            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>11</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Data>
                    <ns2:Amount GridNumber="56">10.50</ns2:Amount>
                    <ns2:Amount GridNumber="59">31.50</ns2:Amount>
                    <ns2:Amount GridNumber="72">21.00</ns2:Amount>
                    <ns2:Amount GridNumber="81">150.00</ns2:Amount>
                    <ns2:Amount GridNumber="87">50.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env['l10n_be.tax.report.handler'].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-31')
    def test_generate_xml_vat_unit(self):
        company = self.env.company
        company_2 = self.company_data_2['company']
        unit_companies = company + company_2

        company_2.currency_id = company.currency_id

        tax_unit = self.env['account.tax.unit'].create({
            'name': "One unit to rule them all",
            'country_id': company.country_id.id,
            'vat': "BE0477472701",
            'company_ids': [Command.set(unit_companies.ids)],
            'main_company_id': company.id,
        })

        first_tax = self.env['account.tax'].search([('name', '=', '21% M'), ('company_id', '=', self.company_data['company'].id)], limit=1)
        second_tax = self.env['account.tax'].search([('name', '=', '21% M.Cocont'), ('company_id', '=', self.company_data['company'].id)], limit=1)

        # Create and post a move with two move lines to get some data in the report
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'partner_id': self.partner_a.id,
            'invoice_date': '2019-11-12',
            'date': '2019-11-12',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test 1',
                'price_unit': 100,
                'tax_ids': first_tax.ids,
            }), (0, 0, {
                'product_id': self.product_b.id,
                'quantity': 1.0,
                'name': 'product test 2',
                'price_unit': 50,
                'tax_ids': second_tax.ids,
            })]
        })
        move.action_post()

        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})
        options['tax_unit'] = tax_unit.id

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        ref = str(company.partner_id.id) + '112019'

        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">

            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>11</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Data>
                    <ns2:Amount GridNumber="00">0.00</ns2:Amount>
                    <ns2:Amount GridNumber="56">10.50</ns2:Amount>
                    <ns2:Amount GridNumber="59">31.50</ns2:Amount>
                    <ns2:Amount GridNumber="72">21.00</ns2:Amount>
                    <ns2:Amount GridNumber="81">150.00</ns2:Amount>
                    <ns2:Amount GridNumber="87">50.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref
        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-04-15')
    def test_generate_xml_with_prorata(self):
        company = self.env.company
        account_return = self.env['account.return'].create({
            'name': 'BE Tax Return',
            'type_id': self.env.ref('l10n_be_reports.be_vat_return_type').id,
            'company_id': company.id,
            'date_from': '2019-03-01',
            'date_to': '2019-03-31',
        })

        wizard_lock = self.env['l10n_be_reports.vat.return.lock.wizard'].create({
            'return_id': account_return.id,
            'is_prorata_necessary': True,
            'prorata_year': 2019,
            'prorata': 25,
            'prorata_at_100': 50,
            'prorata_at_0': 50,
        })
        with self.allow_pdf_render():
            wizard_lock.action_proceed_with_locking()
        xml_file = account_return.attachment_ids.filtered(lambda a: a.name.endswith(".xml"))

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        # Declaring March month, so 3
        ref = str(company.partner_id.id) + '032019'

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>03</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Deduction>
                    <AdjustedPeriod>2019</AdjustedPeriod>
                    <AdjustedValue>25.00</AdjustedValue>
                    <SpecialAdjustedValue>
                        <moreSpecialProrata>false</moreSpecialProrata>
                        <UseProRataPercentage GridNumber="1">50.00</UseProRataPercentage>
                        <UseProRataPercentage GridNumber="2">50.00</UseProRataPercentage>
                        <UseProRataPercentage GridNumber="3">0.00</UseProRataPercentage>
                    </SpecialAdjustedValue>
                </ns2:Deduction>
                <ns2:Data>
                    <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_attachment(xml_file),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2019-12-15')
    def test_tax_return_recon(self):
        tax = self.env['account.tax'].search([('name', '=', '21%'), ('company_id', '=', self.company_data['company'].id)], limit=1)

        # Create and post a move to have non-zero tax return
        move_out = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': self.company_data['default_journal_sale'].id,
            'partner_id': self.partner_a.id,
            'invoice_date': '2019-11-15',
            'date': '2019-11-15',
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 100,
                'tax_ids': tax.ids,
            })]
        })
        move_out.action_post()

        account_return = self.env['account.return'].create({
            'name': 'BE Tax Return',
            'type_id': self.env.ref('l10n_be_reports.be_vat_return_type').id,
            'company_id': self.company_data['company'].id,
            'date_from': '2019-11-01',
            'date_to': '2019-11-30',
        })
        wizard_lock = self.env['l10n_be_reports.vat.return.lock.wizard'].create({
            'return_id': account_return.id,
        })
        with self.allow_pdf_render():
            wizard_lock.action_proceed_with_locking()

        action = account_return._proceed_with_submission()
        vat_wizard = self.env[action['res_model']].browse(action['res_id'])
        vat_wizard.action_mark_as_paid()

        tax_closing_move = account_return.closing_move_ids
        self.assertTrue(tax_closing_move, "A tax closing move should have been created when paying the tax return.")

        # Create a bank transaction to reconcile with the tax closing move
        bank_statement_line = self.env['account.bank.statement.line'].create({
            'date': '2019-12-15',
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_ref': vat_wizard.communication,
            'partner_id': self.env.ref('l10n_be_reports.partner_fps_belgium').id,
            'amount': -vat_wizard.amount_to_pay,
        })
        self.env['account.bank.statement.line']._cron_try_auto_reconcile_statement_lines(batch_size=100)

        tax_payable_account = self.env['account.chart.template'].ref('a4512')

        bank_transaction_move = bank_statement_line.move_id
        self.assertTrue(bank_transaction_move, "A bank transaction move should have been created for the bank statement line.")

        reconciled_lines = tax_closing_move.line_ids.filtered(lambda line: line.account_id == tax_payable_account and line.reconciled)
        self.assertEqual(len(reconciled_lines), 1, "The tax closing move lines should be reconciled after paying the tax return.")

        reconciled_bank_lines = bank_transaction_move.line_ids.filtered(lambda line: line.account_id == tax_payable_account and line.reconciled)
        self.assertEqual(len(reconciled_bank_lines), 1, "The bank transaction move lines should be reconciled.")

        self.assertEqual(reconciled_lines, reconciled_bank_lines.reconciled_lines_ids)
        self.assertEqual(reconciled_lines.reconciled_lines_ids, reconciled_bank_lines)

    def test_be_vat_communication(self):
        """ Test structured communication generation for BE and non-BE VATs. """
        wizard = self.env['qr.code.payment.wizard']
        communication = wizard._be_company_vat_communication(self.company)
        self.assertEqual(communication, '+++047/7472/70195+++', "A BE company should generate a structured communication.")
        self.company.vat = "0470995079"
        communication = wizard._be_company_vat_communication(self.company)
        self.assertEqual(communication, '+++047/0995/07936+++', "A BE company with numeric VAT should generate a structured communication.")

        # Non-BE VAT: no structured communication, should return empty communication
        non_be_company = self.env['res.company'].create({'name': 'Company Non-BE', 'vat': "US08972236"})
        communication = wizard._be_company_vat_communication(non_be_company)
        self.assertEqual(communication, "", "A non-BE company should return an empty communication string.")
        self.company.account_fiscal_country_id = self.env.ref('base.be')
        communication = wizard._be_company_vat_communication(non_be_company)
        self.assertEqual(communication, "", "A non-BE company with fiscal country BE should return an empty communication string.")

    @freeze_time('2019-12-31')
    def test_client_nihil_set_to_no_before_last_year_report(self):
        """
            Ensure client nihil is NO for reports that are not the final one of the calendar year
        """
        company = self.env.company
        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})

        account_return = self.env['account.return'].create({
            'name': 'BE Tax Return',
            'type_id': self.env.ref('l10n_be_reports.be_vat_return_type').id,
            'company_id': company.id,
            'date_from': '2019-11-01',
            'date_to': '2019-11-30',
        })

        wizard = self.env['l10n_be_reports.vat.return.lock.wizard'].create({
            'return_id': account_return.id,
        })

        options = {**options, **(wizard._get_submission_options_to_inject())}

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        # Declaring November 2019, so 112019
        ref = str(company.partner_id.id) + '112019'

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>11</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Data>
                    <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>NO</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )

    @freeze_time('2020-01-31')
    def test_client_nihil_set_to_yes_for_last_year_report(self):
        """
            Ensure client nihil is YES for reports that are the final one of the calendar year
        """
        company = self.env.company
        report = self.env.ref('l10n_be.tax_report_vat')
        options = report.get_options({})

        account_return = self.env['account.return'].create({
            'name': 'BE Tax Return',
            'type_id': self.env.ref('l10n_be_reports.be_vat_return_type').id,
            'company_id': company.id,
            'date_from': '2019-12-01',
            'date_to': '2019-12-31',
        })

        wizard = self.env['l10n_be_reports.vat.return.lock.wizard'].create({
            'return_id': account_return.id,
        })

        options = {**options, **(wizard._get_submission_options_to_inject())}

        # The partner id is changing between execution of the test so we need to append it manually to the reference.
        # Declaring December 2019, so 122019
        ref = str(company.partner_id.id) + '122019'

        # This is the minimum expected from the belgian tax report xml.
        # As no values are in the report, we only find the grid 71 which is always expected to be present.
        expected_xml = """
        <ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
            <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%s">
                <ns2:Declarant>
                    <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">0477472701</VATNumber>
                    <Name>company_1_data</Name>
                    <Street></Street>
                    <PostCode></PostCode>
                    <City></City>
                    <CountryCode>BE</CountryCode>
                    <EmailAddress>jsmith@mail.com</EmailAddress>
                    <Phone>+32475123456</Phone>
                </ns2:Declarant>
                <ns2:Period>
                    <ns2:Month>12</ns2:Month>
                    <ns2:Year>2019</ns2:Year>
                </ns2:Period>
                <ns2:Data>
                    <ns2:Amount GridNumber="71">0.00</ns2:Amount>
                </ns2:Data>
                <ns2:ClientListingNihil>YES</ns2:ClientListingNihil>
                <ns2:Ask Restitution="NO"/>
            </ns2:VATDeclaration>
        </ns2:VATConsignment>
        """ % ref

        self.assertXmlTreeEqual(
            self.get_xml_tree_from_string(self.env[report.custom_handler_model_name].export_tax_report_to_xml(options)['file_content']),
            self.get_xml_tree_from_string(expected_xml)
        )
