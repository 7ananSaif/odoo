from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account_transfer.tests.account_transfer_test_classes import AccountAutoTransferTestCase


# ############################################################################ #
#                                UNIT TESTS                                    #
# ############################################################################ #
@tagged('post_install', '-at_install')
class MoveModelLineTestCase(AccountAutoTransferTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transfer_model.write({
            'account_ids': [Command.link(account.id) for account in cls.origin_accounts],
        })

    def test_get_transfer_move_lines_values_partner(self):
        """
        Create account moves and transfer, verify that the result of the auto transfer is correct.
        """
        amounts = [4242.0, 1234.56]
        partner_ids = [self._create_partner('partner' + str(i)) for i in range(2)]
        self._create_basic_move(
            cred_account=self.destination_accounts[2].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
            partner_id=partner_ids[0].id,
            date_str='2019-02-01',
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[3].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[1],
            partner_id=partner_ids[1].id,
            date_str='2019-02-01',
        )
        transfer_model_line_1 = self._add_transfer_model_line(account_id=self.destination_accounts[3].id, percent=50)
        transfer_model_line_2 = self._add_transfer_model_line(account_id=self.destination_accounts[2].id, percent=50)

        self.assertEqual(transfer_model_line_1.transfer_model_id, transfer_model_line_2.transfer_model_id, 'Only one transfer model should be created for both lines')
        args = [fields.Date.to_date('2019-01-01'), fields.Date.to_date('2019-12-19')]
        res = transfer_model_line_1.transfer_model_id._get_transfer_move_lines_values(*args)
        exp = [
            {
                'name': 'Transfer (100.0% from MASTER 1)',
                'account_id': self.origin_accounts[0].id,
                'date_maturity': args[1],
                'balance': -self.round(sum(amounts)),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 5)',
                'account_id': self.destination_accounts[3].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) / 2),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 4)',
                'account_id': self.destination_accounts[2].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) / 2),
            },
        ]
        self.assertListEqual(exp, res)

    def test_get_transfer_move_lines_values_incomplete(self):
        amounts = [4242.42, 1234.56]
        self._create_basic_move(
            cred_account=self.destination_accounts[0].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[1].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[1],
        )
        percentages = [50, 30]
        transfer_model_line_1 = self._add_transfer_model_line(account_id=self.destination_accounts[0].id, percent=percentages[0])
        transfer_model_line_2 = self._add_transfer_model_line(account_id=self.destination_accounts[1].id, percent=percentages[1])

        self.assertEqual(transfer_model_line_1.transfer_model_id, transfer_model_line_2.transfer_model_id, 'Only one transfer model should be created for both lines')
        args = [fields.Date.to_date('2019-01-01'), fields.Date.to_date('2019-12-19')]
        res = transfer_model_line_1.transfer_model_id._get_transfer_move_lines_values(*args)
        exp = [
            {
                'name': 'Transfer (80.0% from MASTER 1)',
                'account_id': self.origin_accounts[0].id,
                'date_maturity': args[1],
                'balance': -self.round(sum(amounts) * (sum(percentages) / 100.0)),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 2)',
                'account_id': self.destination_accounts[0].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) * (percentages[0] / 100.0)),
            },
            {
                'name': 'Transfer (-30.0% to SLAVE 3)',
                'account_id': self.destination_accounts[1].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) * (percentages[1] / 100.0)),
            }
        ]
        self.assertListEqual(exp, res, 'Only first transfer model line should be handled, second should get 0 and thus not be added')

    def test_get_transfer_move_lines_values_smaller_percentages_and_remainder(self):
        amounts = [4242.42, 1234.56]
        self._create_basic_move(
            cred_account=self.destination_accounts[0].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[1].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[1],
        )
        percentages = [94.9, 4.5, 0.5, 0.1]
        transfer_model_lines = self.env['account.transfer.model.line']
        transfer_lines_amounts = []
        for account, percent in zip(self.destination_accounts, percentages):
            transfer_model_lines |= self._add_transfer_model_line(account_id=account.id, percent=percent)
            transfer_lines_amounts.append(self.round(sum(amounts) * (percent / 100.0)))

        args = [fields.Date.to_date('2019-01-01'), fields.Date.to_date('2019-12-19')]
        res = transfer_model_lines[0].transfer_model_id._get_transfer_move_lines_values(*args)
        exp = [
            {
                'name': 'Transfer (100.0% from MASTER 1)',
                'account_id': self.origin_accounts[0].id,
                'date_maturity': args[1],
                # The amount emptied from the source account is not the sum of the transferred amounts but the total amount to be transferred
                # times the sum of the percentages. this is to ensure that the account ends up with a zero balance and not small residuals.
                # In this particular case it ensures the emptied amount is 4242.42 + 1234.56, 5476.98 otherwise, it would have wrongly been 5476.97.
                'balance': -self.round(sum(amounts) * (sum(percentages) / 100.0)),
            },
            {
                'name': 'Transfer (-94.9% to SLAVE 2)',
                'account_id': self.destination_accounts[0].id,
                'date_maturity': args[1],
                'balance': self.round(transfer_lines_amounts[0]),
            },
            {
                'name': 'Transfer (-4.5% to SLAVE 3)',
                'account_id': self.destination_accounts[1].id,
                'date_maturity': args[1],
                'balance': self.round(transfer_lines_amounts[1]),
            },
            {
                'name': 'Transfer (-0.5% to SLAVE 4)',
                'account_id': self.destination_accounts[2].id,
                'date_maturity': args[1],
                'balance': self.round(transfer_lines_amounts[2]),
            },
            {
                'name': 'Transfer (-0.1% to SLAVE 5)',
                'account_id': self.destination_accounts[3].id,
                'date_maturity': args[1],
                # As it is the destination line of the model, its amount is not computed but based on the remaining balance. Therefore, we don't
                # have 'self.round(transfer_lines_amounts[3])' but the difference between what's already been transferred and the total amount.
                # In this particular case, it means a difference of 0.01 between the computed amount (5.48) and the remaining amount (5.49).
                'balance': self.round(sum(amounts) - sum(transfer_lines_amounts[:3])),
            },
        ]
        self.assertListEqual(exp, res, 'Only first transfer model line should be handled, second should get 0 and thus not be added')

    def test_get_transfer_move_lines_values(self):
        amounts = [4242.0, 1234.56]
        self._create_basic_move(
            cred_account=self.destination_accounts[0].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[1].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[1],
        )
        transfer_model_line_1 = self._add_transfer_model_line(account_id=self.destination_accounts[0].id, percent=50)
        transfer_model_line_2 = self._add_transfer_model_line(account_id=self.destination_accounts[1].id, percent=50)

        self.assertEqual(transfer_model_line_1.transfer_model_id, transfer_model_line_2.transfer_model_id, 'Only one transfer model should be created for both lines')
        args = [fields.Date.to_date('2019-01-01'), fields.Date.to_date('2019-12-19')]
        res = transfer_model_line_1.transfer_model_id._get_transfer_move_lines_values(*args)
        exp = [
            {
                'name': 'Transfer (100.0% from MASTER 1)',
                'account_id': self.origin_accounts[0].id,
                'date_maturity': args[1],
                'balance': -self.round(sum(amounts)),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 2)',
                'account_id': self.destination_accounts[0].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) / 2),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 3)',
                'account_id': self.destination_accounts[1].id,
                'date_maturity': args[1],
                'balance': self.round(sum(amounts) / 2),
            }
        ]
        self.assertListEqual(exp, res)

    def test_get_transfer_move_lines_values_same_partner_ids(self):
        """
        Make sure we only process the account moves once.
        Here the second line references a partner already handled in the first one.
        The second transfer should thus not be applied to the account lines already handled by the first transfer.
        """
        amounts = [4242.42, 1234.56]
        partner_ids = [self._create_partner('partner' + str(i)) for i in range(2)]
        self._create_basic_move(
            cred_account=self.destination_accounts[0].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
            partner_id=partner_ids[0].id,
            date_str='2019-02-01',
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[1].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[1],
            partner_id=partner_ids[1].id,
            date_str='2019-02-01',
        )
        self._create_basic_move(
            cred_account=self.destination_accounts[0].id,
            deb_account=self.origin_accounts[0].id,
            amount=amounts[0],
            date_str='2019-02-01',
        )
        transfer_model_line_1 = self._add_transfer_model_line(account_id=self.destination_accounts[0].id, percent=50)
        transfer_model_line_2 = self._add_transfer_model_line(account_id=self.destination_accounts[1].id, percent=50)

        self.assertEqual(transfer_model_line_1.transfer_model_id, transfer_model_line_2.transfer_model_id, 'Only one transfer model should be created for both lines')
        args = [fields.Date.to_date('2019-01-01'), fields.Date.to_date('2019-12-19')]
        res = transfer_model_line_1.transfer_model_id._get_transfer_move_lines_values(*args)
        exp = [
            {
                'name': 'Transfer (100.0% from MASTER 1)',
                'account_id': self.origin_accounts[0].id,
                'date_maturity': args[1],
                'balance': -self.round(amounts[0] * 2 + amounts[1]),
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 2)',
                'account_id': self.destination_accounts[0].id,
                'date_maturity': args[1],
                'balance': self.round(amounts[0] * 2 + amounts[1]) / 2,
            },
            {
                'name': 'Transfer (-50.0% to SLAVE 3)',
                'account_id': self.destination_accounts[1].id,
                'date_maturity': args[1],
                'balance': self.round(amounts[0] * 2 + amounts[1]) / 2,
            }
        ]
        self.assertListEqual(exp, res, 'Only first transfer model line should be handled, second should get 0 and thus not be added')
