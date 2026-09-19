# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.l10n_ph.tests.common import TestPhCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import Command, fields
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSLSPGeneration(TestAccountReportsCommon, TestPhCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('ph')
    def setUpClass(cls):
        super().setUpClass()

        ChartTemplate = cls.env["account.chart.template"].with_company(cls.company_data["company"])
        # SLS
        tax_sale_exempt = ChartTemplate.ref('l10n_ph_tax_sale_0_exempt')
        tax_sale_zero_rated = ChartTemplate.ref('l10n_ph_tax_sale_0_zr')
        tax_sale_goods = ChartTemplate.ref('l10n_ph_tax_sale_12')

        # SLP
        tax_purchase_exempt = ChartTemplate.ref('l10n_ph_tax_purchase_0_exempt')
        tax_purchase_zero_rated = ChartTemplate.ref('l10n_ph_tax_purchase_0_zr')
        tax_purchase_service = ChartTemplate.ref('l10n_ph_tax_purchase_12_s')
        tax_purchase_capital_goods = ChartTemplate.ref('l10n_ph_tax_purchase_12_c')
        tax_purchase_pit = ChartTemplate.ref('l10n_ph_tax_purchase_4_pit')
        tax_purchase_goods = ChartTemplate.ref('l10n_ph_tax_purchase_12')
        tax_purchase_nr_service = ChartTemplate.ref('l10n_ph_tax_purchase_12_s_nr')
        tax_purchase_ncr = ChartTemplate.ref('l10n_ph_tax_purchase_12_ncr')

        invoice_data = [
            # Sales
            ('out_invoice', cls.partner_c, '2024-02-16', [(300, tax_sale_goods)]),
            ('out_invoice', cls.partner_c, '2024-02-15', [(300, False)]),  # No tax grids so ignored in the report
            ('out_invoice', cls.partner_a, '2024-01-15', [(250, tax_sale_goods), (200, tax_sale_exempt)]),
            ('out_invoice', cls.partner_b, '2024-01-15', [(500, tax_sale_goods), (100, tax_sale_zero_rated)]),
            # Purchases
            ('in_invoice', cls.partner_c, '2024-02-16', [(300, tax_purchase_goods)]),
            ('in_invoice', cls.partner_a, '2024-02-15', [(300, False)]),  # No tax grids so ignored in the report
            ('in_invoice', cls.partner_a, '2024-01-15', [
                (250, tax_purchase_goods),
                (200, tax_purchase_exempt),
                (50, tax_purchase_service),
            ]),
            ('in_invoice', cls.partner_b, '2024-01-15', [
                (500, tax_purchase_goods),
                (100, tax_purchase_zero_rated),
                (250, tax_purchase_capital_goods),
            ]),
            ('in_invoice', cls.partner_c, '2024-01-15', [
                (250, tax_purchase_goods),
                (500, tax_purchase_pit),
                (400, tax_purchase_nr_service),
                (300, tax_purchase_ncr),
            ]),
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

    def test_export_slp(self):
        report = self.env.ref('l10n_ph_reports.slp_report')
        options = self._generate_options(report, fields.Date.from_string('2024-01-01'), fields.Date.from_string('2024-03-31'))
        report_handler = self.env['l10n_ph.slp.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SLSP',
           'form_type_code': 'P',
           'periodicity': 'quarterly',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "123456789P032024.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['H', 'P', '123456789', '"Test Company"', '""', '""', '""', '"Test Company"', '"8 Super Street"', '"Super City False"', '200.00', '100.00', '450.00', '250.00', '2100.00', '296.00', '240.00', '56.00', '', '03/31/2024'],
                # Details
                ['D', 'P', '789456123', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '"9 Super Street"', '"Super City False"', '200.00', '0.00', '50.00', '0.00', '250.00', '36.00', '123456789', '03/31/2024'],
                ['D', 'P', '789456123', '"Test Partner Company"', '""', '""', '""', '"10 Super Street"', '"Super City False"', '0.00', '100.00', '400.00', '250.00', '1850.00', '260.00', '123456789', '03/31/2024']
            ],
        )

    def test_export_sls(self):
        report = self.env.ref('l10n_ph_reports.sls_report')
        options = self._generate_options(report, fields.Date.from_string('2024-01-01'), fields.Date.from_string('2024-03-31'))
        report_handler = self.env['l10n_ph.sls.report.handler']

        # Adds in the data that the wizard would add
        options.update({
           'alpha_type': 'SLSP',
           'form_type_code': 'S',
           'periodicity': 'quarterly',
           'filename_date_format': '%m%Y',
        })

        file_data = report_handler.export_report_to_dat(options)
        self.assertEqual(file_data['file_name'], "123456789S032024.dat")
        self.assertEqual(file_data['file_type'], "dat")

        file_content = file_data['file_content']
        file_data = [row.split(',') for row in file_content.split('\n')]

        self.assertListEqual(
            file_data,
            [
                # Header
                ['H', 'S', '123456789', '"Test Company"', '""', '""', '""', '"Test Company"', '"8 Super Street"', '"Super City False"', '200.00', '100.00', '1050.00', '126.00', '', '03/31/2024'],
                # Details
                ['D', 'S', '789456123', '"Test Partner"', '"Smith"', '"John"', '"Doe"', '"9 Super Street"', '"Super City False"', '200.00', '0.00', '250.00', '30.00', '123456789', '03/31/2024'],
                ['D', 'S', '789456123', '"Test Partner Company"', '""', '""', '""', '"10 Super Street"', '"Super City False"', '0.00', '100.00', '800.00', '96.00', '123456789', '03/31/2024'],
            ]
        )

    def test_registered_name_display_slsp(self):
        report = self.env.ref('l10n_ph_reports.sls_report')
        options = self._generate_options(report, '2024-01-01', '2024-03-31', {'unfold_all': True})
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
