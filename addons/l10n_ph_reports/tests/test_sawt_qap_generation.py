# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.l10n_ph.tests.common import TestPhCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSawtQapGeneration(TestAccountReportsCommon, TestPhCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('ph')
    def setUpClass(cls):
        super().setUpClass()

        cls.withholding_sequence = cls.env['ir.sequence'].create({
            'implementation': 'no_gap',
            'name': 'Withholding Sequence',
            'padding': 4,
            'number_increment': 1,
        })

        ChartTemplate = cls.env["account.chart.template"].with_company(cls.company_data["company"])
        # SAWT
        tax_sale_wi011 = ChartTemplate.ref('l10n_ph_tax_sale_10_wi011')
        tax_sale_12 = ChartTemplate.ref('l10n_ph_tax_sale_12')

        # QAP
        tax_purchase_wi011 = ChartTemplate.ref('l10n_ph_tax_purchase_10_wi011')
        tax_purchase_wi011_ex = ChartTemplate.ref('l10n_ph_tax_purchase_10_wi011_exempt')
        tax_purchase_12 = ChartTemplate.ref('l10n_ph_tax_purchase_12')

        # Set a sequence on the taxes to make it easier to register payments.
        (tax_sale_wi011 | tax_sale_12 | tax_purchase_wi011 | tax_purchase_wi011_ex | tax_purchase_12).withholding_sequence_id = cls.withholding_sequence

        invoice_data = [
            # Sales
            ('out_invoice', cls.partner_a, '2024-07-15', [(250, tax_sale_wi011), (200, tax_sale_wi011)]),
            ('out_invoice', cls.partner_b, '2024-08-15', [(500, tax_sale_wi011)]),
            ('out_invoice', cls.partner_c, '2024-07-15', [(300, tax_sale_12)]),     # No ATC code so ignored in the report
            ('out_invoice', cls.partner_a, '2024-10-10', [(250, tax_sale_wi011)]),
            ('out_invoice', cls.partner_b, '2024-11-25', [(225, tax_sale_wi011)]),
            # Purchases
            ('in_invoice', cls.partner_a, '2024-07-15', [(250, tax_purchase_wi011), (200, tax_purchase_wi011_ex)]),
            ('in_invoice', cls.partner_b, '2024-09-15', [(500, tax_purchase_wi011)]),
            ('in_invoice', cls.partner_c, '2024-07-15', [(300, tax_purchase_12)]),  # No ATC code so ignored in the report
            ('in_invoice', cls.partner_a, '2024-10-18', [(300, tax_purchase_wi011)]),
            ('in_invoice', cls.partner_b, '2024-12-02', [(250, tax_purchase_wi011_ex)]),
        ]

        invoice_vals = []
        for move_type, partner, invoice_date, lines in invoice_data:
            invoice_vals.append({
                'move_type': move_type,
                'invoice_date': invoice_date,
                'partner_id': partner.id,
                'invoice_line_ids': [
                    Command.create({
                        'name': 'Test line',
                        'quantity': 1.0,
                        'price_unit': amount,
                        'tax_ids': tax,
                    }) for amount, tax in lines
                ]
            })
        invoices = cls.env['account.move'].create(invoice_vals)
        invoices.action_post()

        payments = cls.env['account.payment']
        for invoice in invoices:
            payments |= cls.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
                'payment_date': invoice.date,
            })._create_payments()
        cls.env.flush_all()

    def test_export_1701Q(self):
        report = self.env.ref('l10n_ph_reports.sawt_report')
        options = self._generate_options(report, fields.Date.from_string('2024-07-01'), fields.Date.from_string('2024-09-30'))
        report_handler = self.env['l10n_ph.sawt.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SAWT',
           'form_type_code': '1701Q',
           'periodicity': 'quarterly',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "12345678901230920241701Q.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['HSAWT', 'H1701Q', '123456789', '0123', '"Test Company"', '""', '""', '""', '09/2024', ''],
                # Details
                ['DSAWT', 'D1701Q', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '09/2024', '"Prof Fees"', 'WI011', '10.00', '450.00', '45.00'],
                ['DSAWT', 'D1701Q', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', '09/2024', '"Prof Fees"', 'WI011', '10.00', '500.00', '50.00'],
                # Control
                ['CSAWT', 'C1701Q', '123456789', '0123', '09/2024', '950.00', '95.00'],
            ]
        )

    def test_export_1701(self):
        report = self.env.ref('l10n_ph_reports.sawt_report')
        options = self._generate_options(report, fields.Date.from_string('2024-01-01'), fields.Date.from_string('2024-12-31'))
        report_handler = self.env['l10n_ph.sawt.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SAWT',
           'form_type_code': '1701',
           'periodicity': 'annually',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "12345678901231220241701.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['HSAWT', 'H1701', '123456789', '0123', '"Test Company"', '""', '""', '""', '12/2024', ''],
                # Details
                ['DSAWT', 'D1701', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '12/2024', '"Prof Fees"', 'WI011', '10.00', '700.00', '70.00'],
                ['DSAWT', 'D1701', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', '12/2024', '"Prof Fees"', 'WI011', '10.00', '725.00', '72.50'],
                # Control
                ['CSAWT', 'C1701', '123456789', '0123', '12/2024', '1425.00', '142.50'],
            ]
        )

    def test_export_1702Q(self):
        report = self.env.ref('l10n_ph_reports.sawt_report')
        options = self._generate_options(report, fields.Date.from_string('2024-10-01'), fields.Date.from_string('2024-12-31'))
        report_handler = self.env['l10n_ph.sawt.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SAWT',
           'form_type_code': '1702Q',
           'periodicity': 'quarterly',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "12345678901231220241702Q.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['HSAWT', 'H1702Q', '123456789', '0123', '"Test Company"', '""', '""', '""', '12/2024', ''],
                # Details
                ['DSAWT', 'D1702Q', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '12/2024', '"Prof Fees"', 'WI011', '10.00', '250.00', '25.00'],
                ['DSAWT', 'D1702Q', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', '12/2024', '"Prof Fees"', 'WI011', '10.00', '225.00', '22.50'],
                # Control
                ['CSAWT', 'C1702Q', '123456789', '0123', '12/2024', '475.00', '47.50'],
            ]
        )

    def test_export_1702(self):
        report = self.env.ref('l10n_ph_reports.sawt_report')
        options = self._generate_options(report, fields.Date.from_string('2024-01-01'), fields.Date.from_string('2024-12-31'))
        report_handler = self.env['l10n_ph.sawt.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SAWT',
           'form_type_code': '1702',
           'periodicity': 'annually',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "12345678901231220241702.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['HSAWT', 'H1702', '123456789', '0123', '"Test Company"', '""', '""', '""', '12/2024', ''],
                # Details
                ['DSAWT', 'D1702', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '12/2024', '"Prof Fees"', 'WI011', '10.00', '700.00', '70.00'],
                ['DSAWT', 'D1702', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', '12/2024', '"Prof Fees"', 'WI011', '10.00', '725.00', '72.50'],
                # Control
                ['CSAWT', 'C1702', '123456789', '0123', '12/2024', '1425.00', '142.50'],
            ]
        )

    def test_export_1601EQ(self):
        report = self.env.ref('l10n_ph_reports.qap_report')
        options = self._generate_options(report, fields.Date.from_string('2024-07-01'), fields.Date.from_string('2024-09-30'))
        report_handler = self.env['l10n_ph.qap.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'QAP',
           'form_type_code': '1601EQ',
           'periodicity': 'quarterly',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "12345678901230920241601EQ.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['HQAP', 'H1601EQ', '123456789', '0123', '"Test Company"', '09/2024', ''],
                # Detail schedule 1
                ['D1', '1601EQ', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '09/2024', 'WI011', '10.00', '250.00', '25.00'],
                ['D1', '1601EQ', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', '09/2024', 'WI011', '10.00', '500.00', '50.00'],
                # Control schedule 1
                ['C1', '1601EQ', '123456789', '0123', '09/2024', '750.00', '75.00'],
                # Detail schedule 2
                ['D2', '1601EQ', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '09/2024', 'WI011', '200.00'],
                # Control schedule 2
                ['C2', '1601EQ', '123456789', '0123', '09/2024', '200.00'],
            ]
        )

    def test_export_1604E(self):
        report = self.env.ref('l10n_ph_reports.qap_report')
        options = self._generate_options(report, fields.Date.from_string('2024-07-01'), fields.Date.from_string('2024-12-31'))
        report_handler = self.env['l10n_ph.qap.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'QAP',
           'form_type_code': '1604E',
           'periodicity': 'annually',
           'filename_date_format': '%m%d%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "1234567890123123120241604E.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['H1604E', '123456789', '0123', '12/31/2024'],
                # Details schedule 3
                ['D3', '1604E', '123456789', '0123', '12/31/2024', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', 'WI011', '550.00', '10.00', '55.00'],
                ['D3', '1604E', '123456789', '0123', '12/31/2024', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', 'WI011', '500.00', '10.00', '50.00'],
                # Control schedule 3
                ['C3', '1604E', '123456789', '0123', '12/31/2024', '105.00'],
                # Details schedule 4
                ['D4', '1604E', '123456789', '0123', '12/31/2024', '0', '789456123', '0789', '"Test Partner"', '"Smith"', '"John"', '"Doe"', 'WI011', '200.00'],
                ['D4', '1604E', '123456789', '0123', '12/31/2024', '1', '789456123', '0456', '"Test Partner Company"', '""', '""', '""', 'WI011', '250.00'],
                # Control schedule 4
                ['C4', '1604E', '123456789', '0123', '12/31/2024', '450.00'],
            ]
        )

    def test_registered_name_display_sawt(self):
        report = self.env.ref('l10n_ph_reports.sawt_report')
        options = self._generate_options(report, '2024-01-01', '2024-12-31', {'unfold_all': True})
        lines = report._get_lines(options)

        # Find lines for partners
        partner_lines = {}
        for line in lines:
            if line.get('caret_options') == 'res.partner':
                partner_id = report._get_res_id_from_line_id(line['id'], 'res.partner')
                partner_lines[partner_id] = line

        line_a = partner_lines[self.partner_a.id]
        self.assertEqual(line_a['name'], 'John Doe Smith')  # check partner_name
        self.assertEqual(line_a['columns'][1]['name'], 'Smith John Doe')  # check register_name

        line_b = partner_lines[self.partner_b.id]
        self.assertEqual(line_b['name'], 'Test Partner Company')  # check partner_name
        self.assertEqual(line_b['columns'][1]['name'], 'Test Partner Company')  # check register_name
