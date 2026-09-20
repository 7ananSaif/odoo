from odoo import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class AccountAutoTransferTestCase(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env['account.journal'].create({'type': 'bank', 'name': 'bank', 'code': 'BANK'})
        cls.transfer_model = cls.env['account.transfer.model'].create({
            'name': 'Test Transfer',
            'date_start': '2019-06-01',
            'frequency': 'month',
            'journal_id': cls.journal.id
        })

        cls.master_account_index = 0
        cls.slave_account_index = 1
        cls.origin_accounts, cls.destination_accounts = cls._create_accounts(cls)
        cls.round = cls.env.company.currency_id.round

    def _create_accounts(self, amount_of_master_accounts=2, amount_of_slave_accounts=4):
        master_ids = self.env['account.account']

        for _i in range(amount_of_master_accounts):
            self.master_account_index += 1
            master_ids += self.env['account.account'].create({
                'name': 'MASTER %s' % self.master_account_index,
                'code': 'MA00%s' % self.master_account_index,
                'account_type': 'asset_receivable',
                'reconcile': True
            })

        slave_ids = self.env['account.account']
        for _i in range(amount_of_slave_accounts):
            self.slave_account_index += 1
            slave_ids += self.env['account.account'].create({
                'name': 'SLAVE %s' % self.slave_account_index,
                'code': 'SL000%s' % self.slave_account_index,
                'account_type': 'asset_receivable',
                'reconcile': True
            })
        return master_ids, slave_ids

    def _create_partner(self, name="partner01"):
        return self.env['res.partner'].create({'name': name})

    def _create_basic_move(self, cred_account=None, deb_account=None, amount=0, date_str='2019-02-01', partner_id=False, transfer_model_id=False, journal_id=False, posted=True):
        move_vals = {
            'date': date_str,
            'transfer_model_id': transfer_model_id,
            'line_ids': [
                Command.create({
                    'account_id': cred_account or self.origin_accounts[0].id,
                    'credit': amount,
                    'partner_id': partner_id,
                }),
                Command.create({
                    'account_id': deb_account or self.origin_accounts[1].id,
                    'debit': amount,
                    'partner_id': partner_id,
                }),
            ]
        }
        if journal_id:
            move_vals['journal_id'] = journal_id
        move = self.env['account.move'].create(move_vals)
        if posted:
            move.action_post()
        return move

    def _add_transfer_model_line(self, account_id: int = False, percent: float = 100.0):
        account_id = account_id or self.destination_accounts[0].id
        return self.env['account.transfer.model.line'].create({
            'percent': percent,
            'account_id': account_id,
            'transfer_model_id': self.transfer_model.id,
        })
