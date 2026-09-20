from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import fields, Command
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nEsAccountReportTrialBalance(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country('es')
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('l10n_es_reports.l10n_es_reports_trial_balance')
        cls.expense_account = cls.company_data['default_account_expense']
        cls.rec_account = cls.company_data['default_account_receivable']

    def test_l10n_es_trial_balance_with_period_total(self):
        """
            Test the variant of the trial balance which has a "Period Total" column
        """
        move_2023 = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': fields.Date.from_string('2023-01-01'),
            'line_ids': [
                Command.create({
                    'debit': 500.0,
                    'credit': 0.0,
                    'name': 'move_2023_1',
                    'account_id': self.expense_account.id
                }),
                Command.create({
                    'debit': 0.0,
                    'credit': 500.0,
                    'name': 'move_2023_2',
                    'account_id': self.rec_account.id
                }),
            ],
        }])
        move_2023.action_post()

        move_2024 = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': fields.Date.from_string('2024-01-01'),
            'line_ids': [
                Command.create({
                    'debit': 1000.0,
                    'credit': 0.0,
                    'name': 'move_2024_1',
                    'account_id': self.expense_account.id
                }),
                Command.create({
                    'debit': 0.0,
                    'credit': 1000.0,
                    'name': 'move_2024_2',
                    'account_id': self.rec_account.id
                }),
            ],
        }])
        move_2024.action_post()

        options = self._generate_options(self.report, '2024-01-01', '2024-12-31', default_options={'hierarchy': False})

        self.assertLinesValues(
            self.report._get_lines(options),
            #                                                       [  Initial  ]  [                2023             ]    [ End Balance ]
            #    Name                                                 Balance       Debit       Credit    Period Total       Balance
            [0,                                                        1,            2,          3,            4,               5],
            [
                (self.rec_account.display_name,                        -500.0,          0.0,     1000.0,       -1000.0,        -1500.0),
                (self.expense_account.display_name,                       0.0,       1000.0,        0.0,        1000.0,         1000.0),
                ('Undistributed Profits/Losses - company_1_data',       500.0,          0.0,        0.0,           0.0,          500.0),
                ('Total',                                                 0.0,       1000.0,     1000.0,           0.0,            0.0),
            ],
            options,
        )
