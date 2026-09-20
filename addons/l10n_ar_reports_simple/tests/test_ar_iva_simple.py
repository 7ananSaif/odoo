# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from freezegun import freeze_time

from odoo.exceptions import RedirectWarning
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.l10n_ar_reports.tests.test_reports import (
    TestReports as TestARReportsCommon,
)

_logger = logging.getLogger(__name__)


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSimpleReports(TestARReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_ar_arca_activity_id = cls.env.ref("l10n_ar_reports_simple.activity_620100")

    def _test_csv_file(self, filename, file_type):
        ReportHandler = self.env['l10n_ar.tax.report.handler']
        move_ids = ReportHandler._vat_simple_get_csv_move_ids(self.options, file_type)
        if move_ids:
            file_data = ReportHandler._vat_simple_get_data(file_type, move_ids).strip()
            res_file = file_open('l10n_ar_reports_simple/tests/' + filename, 'rb').read().decode().strip()
            self.assertEqual(file_data, res_file)

    def test_01_sale_only_simple_report(self):
        self.options['ar_vat_book_tax_types_available']['sale']['selected'] = True
        self.options['ar_vat_book_tax_types_available']['purchase']['selected'] = False
        self._test_csv_file('SaleRefund.csv', 'sale_refund')
        self._test_csv_file('SaleInvoice.csv', 'sale_invoice')

    def test_02_purchase_only_simple_report(self):
        self.options['ar_vat_book_tax_types_available']['sale']['selected'] = False
        self.options['ar_vat_book_tax_types_available']['purchase']['selected'] = True
        self._test_csv_file('PurchaseRefund.csv', 'purchase_refund')
        self._test_csv_file('PurchaseInvoice.csv', 'purchase_invoice')

    def test_03_missing_fallback_activity(self):
        """ If there is no fallback on the company, a warning should be raised when trying to export the files. """
        self.env.company.l10n_ar_arca_activity_id = False
        self.options['ar_vat_book_tax_types_available']['sale']['selected'] = True
        with self.assertRaisesRegex(
            RedirectWarning,
            "Warning, activities are not set as a fallback on the company. As such the Sales VAT Simple files may be incorrect. Please set a fallback activity on the company or ignore this warning to generate the file anyway.",
        ):
            self.env['l10n_ar.tax.report.handler'].vat_simple_export_files_to_zip(self.options)

    @freeze_time('2024-01-01')
    def test_04_mixed_sale_taxes(self):
        """ VAT Simple tax reports should only include tax values that are of type IVA. Any other
            taxes should be skipped over. (We use a different date to just check this record versus
            all the rest)"""
        self.options['ar_vat_book_tax_types_available']['sale']['selected'] = True
        self.options['date']['date_from'] = '2024-01-01'
        self.options['date']['date_to'] = '2024-01-31'

        self.tax_perc_iibb.active = True
        self.tax_perc_iibb.amount = 3
        invoice = self._create_invoice_from_dict({
            "move_type": 'out_invoice',
            "partner_id": self.res_partner_servicios_globales,
            "date": '2024-01-01',
            "invoice_date": '2024-01-01',
            "invoice_line_ids": [
                {'product_id': self.product_iva_105_perc, 'price_unit': 10000.0, 'quantity': 1},
            ],
        })
        invoice.action_post()
        self._test_csv_file('SaleInvoiceMixed.csv', 'sale_invoice')
