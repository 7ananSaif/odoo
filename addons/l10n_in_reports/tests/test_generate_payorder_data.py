from odoo.addons.account.tests.test_account_payment import TestAccountPayment
from odoo import SUPERUSER_ID
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestGeneratePayorderData(TestAccountPayment):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')

        cls.enet_rtgs_method_id = cls.env.ref('l10n_in_reports.account_payment_method_enet_rtgs').id

        cls.bank_journal_1.outbound_payment_method_line_ids |= cls.env['account.payment.method.line'].create(
            {"payment_method_id": cls.enet_rtgs_method_id}
        )
        cls.enet_rtgs_line_bank_journal_1 = cls.bank_journal_1.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'enet_rtgs')

        cls.enet_bank_template = cls.env['enet.bank.template'].with_user(SUPERUSER_ID).create({
            'name': 'Dummy Bank',
            'include_header': True,
            'bank_configuration': [
                {
                    'field_name': 'payment_method_line_id.code',
                    'label': 'Transaction Type',
                    'mapping': {'enet_rtgs': 'R'}
                },
                {
                    'field_name': 'partner_id.name',
                    'label': 'Beneficiary Name',
                },
                {
                    'field_name': 'amount',
                    'label': 'Amount'
                },
                {
                    'field_name': 'date',
                    'label': 'Chq/Trn Date',
                    'date_format': '%d/%m/%Y'
                },
                {
                    'field_name': 'partner_bank_id.acc_number',
                    'label': 'Beneficiary Account Number'
                }
            ]
        })
        # Bank Journal Configuration
        cls.bank_journal_1.bank_template_id = cls.enet_bank_template

        # Payments
        cls.payment1 = cls.env['account.payment'].create({
            'amount': 100.0,
            'date': '2025-08-26',
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': cls.partner_a.id,
            'payment_method_line_id': cls.enet_rtgs_line_bank_journal_1.id,
            'journal_id': cls.bank_journal_1.id
        })
        cls.payment1.partner_bank_id.allow_out_payment = True
        cls.payment1.action_post()

        cls.payment2 = cls.env['account.payment'].create({
            'amount': 200.0,
            'date': '2025-08-26',
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': cls.partner_a.id,
            'payment_method_line_id': cls.enet_rtgs_line_bank_journal_1.id,
            'journal_id': cls.bank_journal_1.id
        })
        cls.payment2.partner_bank_id.allow_out_payment = True
        cls.payment2.action_post()

        # Batch Payment
        cls.batch_payment = cls.env['account.batch.payment'].create({
            'journal_id': cls.bank_journal_1.id,
            'date': '2025-08-26',
            'payment_ids': [(4, payment.id, None) for payment in (cls.payment1 | cls.payment2)],
            'payment_method_id': cls.enet_rtgs_method_id,
            'batch_type': 'outbound',
        })
        cls.batch_payment.validate_batch()

    # Testing payorder data for a batch
    def test_csv_data(self):
        data = self.batch_payment.get_csv_data().splitlines()

        header = (
            'Transaction Type,Beneficiary Name,Amount,Chq/Trn Date,Beneficiary Account Number'
        )
        self.assertEqual(data[0], header, "Didn't generate the expected header")

        expected_csv_lines = [(
            'R,partner_a,100.0,26/08/2025,0123456789'
        ), (
            'R,partner_a,200.0,26/08/2025,0123456789'
        )]
        self.assertEqual(data[1], expected_csv_lines[0], "Didn't generate the expected lines for Payment1")
        self.assertEqual(data[2], expected_csv_lines[1], "Didn't generate the expected lines for Payment2")
        self.assertEqual(len(data), 3, "It should exactly generate the three lines above")
