# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_sepa_direct_debit.tests.common import SepaDirectDebitCommon


@tagged('post_install', '-at_install')
class TestSepaDirectDebitMain(SepaDirectDebitCommon, PaymentHttpCommon):

    def test_sdd_set_mandate_updates_tx(self):
        tx = self._create_transaction(flow='direct', provider_code='custom')
        url = self._build_url('/payment/sepa_direct_debit/set_mandate')
        with patch(
            'odoo.addons.payment.utils.check_access_token', return_value=True
        ), patch(
            'odoo.addons.payment_sepa_direct_debit.controllers.main.SepaDirectDebitController'
            '._sdd_validate_and_format_iban', return_value='test_iban'
        ), patch(
            'odoo.addons.payment_sepa_direct_debit.models.payment_provider.PaymentProvider'
            '._sdd_find_or_create_mandate', return_value=self.mandate
        ):
            self.make_jsonrpc_request(url, params=dict(
                reference=tx.reference,
                iban='test_iban',
                access_token='test_access_token',
            ))
        self.assertTrue(tx.mandate_id)
        self.assertEqual(tx.state, 'pending')
