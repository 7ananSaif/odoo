from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import fields, Command
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nCoReportsTrialBalanceReport(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country('co')
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_a.vat = '11111'
        cls.partner_b.vat = '22222'

        cls.account_asset = cls.env['account.account'].search([
            ('company_ids', '=', cls.company_data['company'].id),
            ('code', '=', '112000')
        ], limit=1)
        cls.account_asset_name = cls.account_asset.display_name
        cls.account_receivable_name = cls.company_data['default_account_receivable'].display_name

        cls.report = cls.env.ref('l10n_co_reports.l10n_co_reports_trial_balance_per_partner')
        cls.company_data['company'].totals_below_sections = False

    def test_trial_balance_groupby_partner_id(self):
        """
            Test the variant of the trial balance which has
                - a sub-groupby on partner_id
                - a partner vat column
                - no details per partner for the unaffected earnings
        """
        move_q4_2022 = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': fields.Date.from_string('2022-12-01'),
            'line_ids': [
                Command.create({
                    'partner_id': self.partner_a.id,
                    'debit': 1000.0,
                    'credit': 0.0,
                    'name': 'move_line_1',
                    'account_id': self.account_asset.id
                }),
                Command.create({
                    'partner_id': self.partner_b.id,
                    'debit': 500.0,
                    'credit': 0.0,
                    'name': 'move_line_2',
                    'account_id': self.account_asset.id
                }),
                Command.create({
                    'partner_id': self.partner_b.id,
                    'debit': 500.0,
                    'credit': 0.0,
                    'name': 'move_line_3',
                    'account_id': self.account_asset.id
                }),
                Command.create({
                    'debit': 1300.0,
                    'credit': 0.0,
                    'name': 'move_line_4',
                    'account_id': self.account_asset.id
                }),
                Command.create({
                    'partner_id': self.partner_a.id,
                    'debit': 0.0,
                    'credit': 3000.0,
                    'name': 'move_line_5',
                    'account_id': self.company_data['default_account_receivable'].id
                }),
                Command.create({
                    'partner_id': self.partner_a.id,
                    'debit': 0.0,
                    'credit': 300.0,
                    'name': 'move_line_6',
                    'account_id': self.company_data['default_account_revenue'].id
                }),
            ],
        }])
        move_q4_2022.action_post()

        options = self._generate_options(self.report, '2023-01-01', '2023-03-31', default_options={'unfold_all': True})

        self.assertLinesValues(
            self.report._get_lines(options),
            #                                                                     [ Initial  ]  [     Q1 2023      ]   [ End Balance ]
            #    Name                                               Partner VAT     Balance     Debit       Credit         Balance
            [0,                                                          1,            2,          3,          4,          5],
            [
                ('1 Assets',),
                ('11 Cash and Cash Equivalents',),
                ('1120 Savings Accounts',),
                (self.account_asset_name,                               '',        3300.0,        0.0,        0.0,       3300.0),

                ('partner_a',                                      '11111',        1000.0,        0.0,        0.0,       1000.0),
                ('partner_b',                                      '22222',        1000.0,        0.0,        0.0,       1000.0),
                ('Unknown',                                             '',        1300.0,        0.0,        0.0,       1300.0),

                ('13 Debtors',),
                ('1305 Clients',),

                (self.account_receivable_name,                          '',       -3000.0,        0.0,        0.0,      -3000.0),
                ('partner_a',                                      '11111',       -3000.0,        0.0,        0.0,      -3000.0),

                ('Undistributed Profits/Losses - company_1_data',       '',        -300.0,        0.0,        0.0,       -300.0),
                ('Total',                                               '',           0.0,        0.0,        0.0,          0.0),
            ],
            options,
        )
