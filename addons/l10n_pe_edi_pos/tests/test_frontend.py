from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged
from odoo import Command


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestUi(TestPeEdiCommon, TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_data['company'].l10n_pe_edi_provider = 'digiflow'
        edi_format = cls.env['account.edi.format'].search([("code", "=", "pe_ubl_2_1")])
        cls.main_pos_config.invoice_journal_id.write({
            "edi_format_ids": [Command.link(edi_format.id)]
        })

    def test_pos_invoice_order_and_refund(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("l10n_pe_edi_pos.RefundWithReasonTour")
