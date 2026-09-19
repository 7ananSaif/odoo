from odoo import Command
from odoo.addons.account_iso20022.tests.test_iso20022_common import TestISO20022CommonCreditTransfer
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestISO20022ChargeBearer(TestISO20022CommonCreditTransfer):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.EUR').active = True
        cls.env.user.group_ids |= cls.env.ref('account.group_validate_bank_account')
        cls.payment_method = cls.env.ref('account_iso20022.account_payment_method_iso20022')
        cls.bank_journal = cls.company_data['default_journal_bank']
        cls.bank_ing = cls.env['res.bank'].create({
            'name': 'ING',
            'bic': 'BBRUBEBB',
        })
        cls.bank_journal.write({
            'bank_id': cls.bank_ing.id,
            'bank_acc_number': 'BE48363523682327',
            'currency_id': cls.env.ref('base.EUR').id,
            'available_payment_method_ids': [Command.link(cls.payment_method.id)],
        })
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create([{
            'name': cls.payment_method.name,
            'payment_method_id': cls.payment_method.id,
            'journal_id': cls.company_data['default_journal_bank'].id
        }])
        cls.env['res.partner.bank'].create({
            'acc_type': 'iban',
            'partner_id': cls.partner_a.id,
            'acc_number': 'BE08429863697813',
            'allow_out_payment': True,
            'bank_id': cls.bank_ing.id,
            'currency_id': cls.env.ref('base.USD').id,
        })
        # A country is required for sepa transfer
        cls.partner_a.country_id = cls.env.ref('base.us')
        cls.partner_b.country_id = cls.env.ref('base.us')

    def test_default_charge_bearer(self):
        """
        The default charge bearer should be 'SHAR'.
        """
        payment = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        sct_doc = self.get_sct_doc_from_batch(batch)
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(charge_bearer, 'SHAR')

    def test_journal_charge_bearer(self):
        """
        The charge bearer should be the one set on the journal.
        """
        self.bank_journal.iso20022_charge_bearer = 'CRED'
        payment = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        sct_doc = self.get_sct_doc_from_batch(batch)
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(charge_bearer, 'CRED')

    def test_payment_charge_bearer(self):
        """
        The charge bearer should be the one set on the payment.
        """
        self.bank_journal.iso20022_charge_bearer = 'CRED'
        payment = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment.iso20022_charge_bearer = 'DEBT'
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        sct_doc = self.get_sct_doc_from_batch(batch)
        charge_bearer = sct_doc.find('.//{*}PmtInf/{*}ChrgBr').text

        self.assertEqual(charge_bearer, 'DEBT')

    def test_payment_multiple_charge_bearers(self):
        """
        The charge bearer should be set on the payments if there are multiple.
        """
        payment_1 = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            500,
        )
        payment_1.iso20022_charge_bearer = 'DEBT'
        payment_1.action_post()

        payment_2 = self.create_payment(
            self.bank_journal,
            self.partner_a,
            None,
            700,
        )
        payment_2.iso20022_charge_bearer = 'CRED'
        payment_2.action_post()

        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [Command.link(payment_1.id), Command.link(payment_2.id)],
            'payment_method_id': self.payment_method.id,
            'batch_type': 'outbound',
        })
        batch.validate_batch()
        sct_doc = self.get_sct_doc_from_batch(batch)

        charge_bearer_1 = sct_doc.find('.//{*}PmtInf/{*}CdtTrfTxInf[1]/{*}ChrgBr').text
        charge_bearer_2 = sct_doc.find('.//{*}PmtInf/{*}CdtTrfTxInf[2]/{*}ChrgBr').text
        self.assertEqual(charge_bearer_1, 'DEBT')
        self.assertEqual(charge_bearer_2, 'CRED')
