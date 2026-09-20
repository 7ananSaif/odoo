# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.addons.l10n_ar_edi.tests.common import TestArEdiMockedCommon


@tagged("post_install", "post_install_l10n", "-at_install")
class TestArEdiMocked(TestArEdiMockedCommon):
    @classmethod
    @TestArEdiMockedCommon.setup_afip_ws('wsfe')
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.res_partner_adhoc
        cls.journal = cls._create_journal(cls, 'wsfe')

    def test_01_invoice_a_product(self):
        with self.patch_client([('FECAESolicitar', 'FECAESolicitar-final', 'FECAESolicitar-final')]):
            self._test_case('invoice_a', 'product')
