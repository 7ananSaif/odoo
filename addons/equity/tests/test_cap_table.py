from odoo.exceptions import UserError

from odoo.addons.equity.tests.common import TestEquityCommon


class TestEquity(TestEquityCommon):
    def test_no_transaction(self):
        self.assertFalse(self.env['equity.cap.table'].search([('partner_id', '=', self.company.id)]))

    def test_shares_equal_class(self):
        self.env['equity.transaction'].create([
            {
                'partner_id': self.company.id,
                'subscriber_id': self.contact_1.id,
                'date': '2010-01-01',
                'transaction_type': 'issuance',
                'securities': 75,
                'security_price': 10,
                'security_class_id': self.share_class_ord.id,
            },
            {
                'partner_id': self.company.id,
                'subscriber_id': self.contact_2.id,
                'date': '2010-01-01',
                'transaction_type': 'issuance',
                'securities': 25,
                'security_price': 7,
                'security_class_id': self.share_class_ord.id,
            },
        ])
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_1.id)]),
            [{
                'securities': 75,
                'votes': 75,
                'ownership': 0.75,
                'voting_rights': 0.75,
                'dividend_payout': 0.75,
                'dilution': 0.75,
                'valuation': 750,
            }],
        )
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_2.id)]),
            [{
                'securities': 25,
                'votes': 25,
                'ownership': 0.25,
                'voting_rights': 0.25,
                'dividend_payout': 0.25,
                'dilution': 0.25,
                'valuation': 250,
            }],
        )

    def test_share_more_vote(self):
        self.env['equity.transaction'].create([
            {
                'partner_id': self.company.id,
                'subscriber_id': self.contact_1.id,
                'date': '2010-01-01',
                'transaction_type': 'issuance',
                'securities': 100,
                'security_price': 10,
                'security_class_id': self.share_class_a.id,
            },
            {
                'partner_id': self.company.id,
                'subscriber_id': self.contact_2.id,
                'date': '2010-01-01',
                'transaction_type': 'issuance',
                'securities': 100,
                'security_price': 10,
                'security_class_id': self.share_class_b.id,
            },
        ])
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_1.id)]),
            [{
                'securities': 100,
                'votes': 200,
                'ownership': 0.5,
                'voting_rights': 0.66666666666666666666666,
            }],
        )
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_2.id)]),
            [{
                'securities': 100,
                'votes': 100,
                'ownership': 0.5,
                'voting_rights': 0.33333333333333333333333,
            }],
        )

    def test_sell_shares(self):
        self.env['equity.transaction'].create([
            {
                'partner_id': self.company.id,
                'subscriber_id': self.contact_1.id,
                'date': '2010-01-01',
                'transaction_type': 'issuance',
                'securities': 100,
                'security_price': 10,
                'security_class_id': self.share_class_ord.id,
            },
            {
                'partner_id': self.company.id,
                'seller_id': self.contact_1.id,
                'subscriber_id': self.contact_2.id,
                'date': '2011-01-01',
                'transaction_type': 'transfer',
                'securities': 30,
                'security_price': 10,
                'security_class_id': self.share_class_ord.id,
            },
        ])
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_1.id)]),
            [{
                'securities': 70,
                'votes': 70,
                'ownership': 0.7,
                'voting_rights': 0.7,
                'dilution': 0.7,
                'valuation': 700,
            }],
        )
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_2.id)]),
            [{
                'securities': 30,
                'votes': 30,
                'ownership': 0.3,
                'voting_rights': 0.3,
                'dilution': 0.3,
                'valuation': 300,
            }],
        )

    def test_option_into_share_exceed(self):
        self.env['equity.transaction'].create([{
            'partner_id': self.company.id,
            'subscriber_id': self.contact_1.id,
            'date': '2010-01-01',
            'expiration_date': '2100-12-31',
            'transaction_type': 'issuance',
            'securities': 100,
            'security_price': 10,
            'security_class_id': self.option_class_1.id,
        }])
        self.env['equity.transaction'].create({
            'partner_id': self.company.id,
            'subscriber_id': self.contact_1.id,
            'date': '2010-01-01',
            'transaction_type': 'exercise',
            'securities': 20,
            'security_price': 10,
            'security_class_id': self.option_class_1.id,
            'destination_class_id': self.share_class_ord.id,
        })

        with self.assertRaisesRegex(UserError, "options available"):
            self.env['equity.transaction'].create([{
                'partner_id': self.company.id,
                'subscriber_id': self.contact_1.id,
                'date': '2010-01-01',
                'transaction_type': 'exercise',
                'securities': 90,
                'security_price': 10,
                'security_class_id': self.share_class_ord.id,
            }])

    def test_option_into_share(self):
        self.env['equity.transaction'].create([{
            'partner_id': self.company.id,
            'subscriber_id': self.contact_1.id,
            'date': '2010-01-01',
            'expiration_date': '2100-12-31',
            'transaction_type': 'issuance',
            'securities': 100,
            'security_price': 10,
            'security_class_id': self.option_class_2.id,
        }])
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id)]),
            [{
                'partner_id': self.company.id,
                'holder_id': self.contact_1.id,
                'security_class_id': self.option_class_2.id,
                'securities': 100,
                'votes': 0,
                'ownership': 0,
                'voting_rights': 0,
                'dilution': 1,
                'valuation': 1000,
            }],
        )

        self.env['equity.transaction'].create([{
            'partner_id': self.company.id,
            'subscriber_id': self.contact_1.id,
            'date': '2011-01-01',
            'transaction_type': 'exercise',
            'securities': 20,
            'security_price': 10,
            'security_class_id': self.option_class_2.id,
            'destination_class_id': self.share_class_a.id,
        }])
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_1.id), ('security_class_id', '=', self.share_class_a.id)]),
            [{
                'securities': 20,
                'votes': 40,
                'ownership': 1,
                'voting_rights': 1,
                'dilution': 0.2,
                'valuation': 200,
            }],
        )
        self.assertRecordValues(
            self.env['equity.cap.table'].search([('partner_id', '=', self.company.id), ('holder_id', '=', self.contact_1.id), ('security_class_id', '=', self.option_class_2.id)]),
            [{
                'securities': 80,
                'votes': 0,
                'ownership': 0,
                'voting_rights': 0,
                'dilution': 0.8,
                'valuation': 800,
            }],
        )

        # Looking in the past, it should still display the old value
        self.assertRecordValues(
            self.env['equity.cap.table'].with_context(current_date='2010-01-01').search([('partner_id', '=', self.company.id)]),
            [{
                'partner_id': self.company.id,
                'holder_id': self.contact_1.id,
                'security_class_id': self.option_class_2.id,
                'securities': 100,
                'votes': 0,
                'ownership': 0,
                'voting_rights': 0,
                'dilution': 1,
                'valuation': 1000,
            }],
        )
