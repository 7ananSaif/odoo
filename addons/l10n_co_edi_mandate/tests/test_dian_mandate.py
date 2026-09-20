from odoo import Command

from odoo.tests import tagged, freeze_time
from odoo.addons.l10n_co_dian.tests.common import TestCoDianCommon


@freeze_time('2024-01-30')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDianMandate(TestCoDianCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_mandate = cls.env['res.partner'].create({
            'name': "MANDATE PARTNER",
            'property_account_receivable_id': cls.company_data['default_account_receivable'].id,
            'property_account_payable_id': cls.company_data['default_account_payable'].id,
            'country_id': cls.env.ref('base.co').id,
            'vat': "2131234321",
            'l10n_latam_identification_type_id': cls.env.ref('l10n_co.rut').id,
        })

        cls.product_a.l10n_co_dian_mandate_contract = True

    def test_invoice_mandate(self):
        invoice = self._create_move(
            l10n_co_dian_mandate_principal=self.partner_mandate.id,
            invoice_line_ids=[
                Command.create({
                    'product_id': self.product_a.id,
                    'price_unit': 100,
                }),
                Command.create({
                    'product_id': self.product_b.id,
                    'price_unit': 100,
                }),
            ],
        )
        xml = self.env['account.edi.xml.ubl_dian']._export_invoice(invoice)[0]
        self._assert_document_dian(xml, "l10n_co_edi_mandate/tests/attachments/invoice_mandate.xml")
