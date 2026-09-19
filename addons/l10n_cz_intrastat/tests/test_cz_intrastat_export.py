from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.account_sales_report_common import AccountSalesReportCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestCZIntrastatExport(AccountSalesReportCommon):

    @classmethod
    @AccountSalesReportCommon.setup_country('cz')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].country_id = cls.env.ref('base.cz')
        cls.company_data['company'].account_fiscal_country_id = cls.env.ref('base.cz')
        cls.company_data['company'].vat = 'CZ12345679'
        cls.report = cls.env.ref('account_intrastat.intrastat_report')
        cls.report_handler = cls.env['account.intrastat.goods.report.handler']

        belgium = cls.env.ref('base.be')

        cls.partner_a = cls.env['res.partner'].create({
            'name': 'SUPER BELGIAN PARTNER',
            'street': 'Rue du Paradis, 10',
            'zip': '6870',
            'city': 'Eghezee',
            'country_id': belgium.id,
            'phone': '061928374',
            'vat': 'BE0897223670',
        })

        cls.product_rocket = cls.env['product.product'].create({
            'name': 'rocket',
            'intrastat_code_id': cls.env.ref('account_intrastat.commodity_code_2018_88023000').id,
            'intrastat_supplementary_unit_amount': 1,
            'weight': 5000,
            'intrastat_origin_country_id': cls.env.ref('base.es').id,
        })
        cls.product_satellite = cls.env['product.product'].create({
            'name': 'satellite',
            'intrastat_code_id': cls.env.ref('account_intrastat.commodity_code_2018_88023000').id,
            'intrastat_supplementary_unit_amount': 2,
            'weight': 0.06,
            'intrastat_origin_country_id': cls.env.ref('base.es').id,
        })

        cls.inwards_vendor_bill = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': '2025-07-15',
            'date': '2025-07-15',
            'intrastat_country_id': belgium.id,
            'intrastat_transport_mode_id': cls.env.ref('account_intrastat.account_intrastat_transport_1').id,
            'company_id': cls.company_data['company'].id,
            'invoice_line_ids': [Command.create({
                'intrastat_transaction_id': cls.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                'product_id': cls.product_rocket.id,
                'quantity': 10,
                'price_unit': 30000,
            })]
        })

        cls.outwards_customer_invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner_a.id,
            'invoice_date': '2025-07-15',
            'date': '2025-07-15',
            'intrastat_country_id': belgium.id,
            'intrastat_transport_mode_id': cls.env.ref('account_intrastat.account_intrastat_transport_2').id,
            'company_id': cls.company_data['company'].id,
            'invoice_line_ids': [Command.create({
                'product_id': cls.product_satellite.id,
                'intrastat_transaction_id': cls.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                'quantity': 4,
                'price_unit': 200,
            })]
        })

        cls.inwards_vendor_bill.action_post()
        cls.outwards_customer_invoice.action_post()

    def test_cz_intrastat_csv_export(self):
        options = self._generate_options(
            self.report,
            '2025-07-01',
            '2025-07-31',
            {'unfold_all': True, 'export_mode': 'file'}
        )

        self.assertLinesValues(
            self.report._get_lines(options),
            # 0/name, 1/system, 2/country, 3/transaction code, 4/region code, 5/commodity code, 6/origin country, 12/value
            [                                            0,                     1,           2,     3,       4,            5,      6,       12],
            [
                (                              'Intrastat',                  None,        None,  None,    None,         None,   None, 300800.0),
                # Arrival invoice
                ( 'Arrival - BE0897223670 - 88023000 - BE',        '29 (Arrival)',   'Belgium',  '11',      '',   '88023000',   'ES',   300000),
                (                      'BILL/2025/07/0001',        '29 (Arrival)',   'Belgium',  '11',      '',   '88023000',   'ES',   300000),
                # Dispatch invoice
                ('Dispatch - BE0897223670 - 88023000 - BE',       '19 (Dispatch)',   'Belgium',  '11',      '',   '88023000',   'ES',      800),
                (                         'INV/2025/00001',       '19 (Dispatch)',   'Belgium',  '11',      '',   '88023000',   'ES',      800),
            ],
            options,
        )

        file = self.report_handler.cz_intrastat_export_to_csv(options)
        self.assertEqual(
            file['file_content'],
            '07;2025;CZ12345679;D;BE0897223670;BE;;ES;11;2;;ST;88023000;;;0.200;8;800;;\n'
            '07;2025;CZ12345679;A;BE0897223670;BE;;ES;11;1;;ST;88023000;;;50000;10;300000;;\n'
        )
