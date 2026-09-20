from odoo.exceptions import UserError

from odoo.addons.esg.tests.esg_common import TestEsgCommon


class TestAccountAccount(TestEsgCommon):

    def test_cannot_create_non_expense_account_from_esg(self):
        """Test that we cannot create an account from ESG that is not an expense account."""
        with self.assertRaises(UserError, msg='You can only create expense accounts from ESG.'):
            self.env['account.account'].with_context(from_emission_factor_line=True).create({
                'name': 'Non Expense Account',
                'code': '999999',
                'account_type': 'asset_current',
            })

    def test_cannot_link_non_expense_account_to_assignation_lines(self):
        """Test that we cannot link a non-expense account to ESG assignation lines."""
        non_expense_account = self.env['account.account'].create({
            'name': 'Non Expense Account',
            'code': '999998',
            'account_type': 'asset_current',
        })
        with self.assertRaises(UserError, msg='You can only assign expense accounts to ESG assignation lines.'):
            self.env['esg.assignation.line'].create({
                'account_id': non_expense_account.id,
                'esg_emission_factor_id': self.emission_factor_foreign_electricity_consumption.id,
            })

    def test_remove_linked_esg_lines_on_changing_account_type(self):
        """Test that ESG assignation lines and emission factors of journal entries are removed when changing the account type to a non-expense type."""
        for account, esg_usable in self.accounts_to_esg_usable.items():
            if not esg_usable:
                continue
            # Test with all usable account types
            with self.subTest(account=account, esg_usable=esg_usable):
                bill_line = self.env['account.move.line'].create({
                    'move_id': self.bill_1.id,
                    'name': 'Foreign Electricity Consumption',
                    'price_unit': 100.0,
                    'esg_emission_factor_id': self.emission_factor_foreign_electricity_consumption.id,
                    'account_id': account.id,
                })
                self.env['esg.assignation.line'].create({
                    'account_id': account.id,
                    'esg_emission_factor_id': self.emission_factor_foreign_electricity_consumption.id,
                })
                self.assertEqual(len(self.emission_factor_foreign_electricity_consumption.assignation_line_ids), 1, 'There should be one assignation line linked to the emission factor.')
                self.assertEqual(len(self.emission_factor_foreign_electricity_consumption.account_move_line_ids), 1, 'There should be one journal entry line linked to the emission factor.')
                account.account_type = 'asset_current'  # Change to a non-expense type
                self.assertFalse(self.emission_factor_foreign_electricity_consumption.assignation_line_ids, 'There should be no more assignation line linked to the emission factor after changing the account type to a non-expense type.')
                self.assertFalse(bill_line.esg_emission_factor_id, 'The emission factor should be removed from the bill line after changing the account type to a non-expense type.')
