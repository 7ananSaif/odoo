from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account_online_synchronization.tests.common import AccountOnlineSynchronizationCommon


@tagged('post_install', '-at_install')
class TestAccountOnlinePaymentActivation(AccountOnlineSynchronizationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_online_link.is_payment_enabled = True
        cls.account_online_link.is_payment_activated = True

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_activating_payment(self, patched_fetch_odoofin):
        patched_fetch_odoofin.side_effect = [
            {'redirect_url': 'redirect_url'},
        ]

        self.account_online_link.is_payment_activated = False

        self.assertEqual(
            self.account_online_link._activate_payments(),
            {
                'type': 'ir.actions.act_url',
                'url': 'redirect_url',
                'target': '_blank',
            }
        )

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_activating_already_activated_payment(self, patched_fetch_odoofin):
        with self.assertRaises(UserError) as context:
            self.account_online_link._activate_payments()
        self.assertEqual(str(context.exception), "Payments are already activated.")
        patched_fetch_odoofin.assert_not_called()

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin')
    def test_activating_a_non_enabled_connection(self, patched_fetch_odoofin):
        self.account_online_link.is_payment_enabled = False
        with self.assertRaises(UserError) as context:
            self.account_online_link._activate_payments()
        self.assertEqual(str(context.exception), "To activate payments, you must first enable them when connecting a bank account.")
        patched_fetch_odoofin.assert_not_called()
