from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDEPoSCert(TestPoSCommon):

    def test_get_cash_statement_cases_trimms_cash_reasons_to_40(self):
        self.basic_config.open_ui()
        current_session = self.basic_config.current_session_id
        current_session.try_cash_in_out(
            "in",
            10,
            "geldtransit-this is a long reason to test that 40+ cash in/out reasons will not break",
            self.partner.id,
            {"formattedAmount": "10.00 €", "translatedType": "in"},
        )

        statements = current_session.get_cash_statement_cases([])
        self.assertEqual([statement for statement in statements if len(statement['name']) > 40], [])
