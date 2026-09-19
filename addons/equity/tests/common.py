from odoo.tests.common import TransactionCase


class TestEquityCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.partner'].create({
            'name': 'Company',
            'is_company': True,
        })
        cls.contact_1 = cls.env['res.partner'].create({
            'name': 'Company Holder 1',
            'is_company': False,
        })
        cls.contact_2 = cls.env['res.partner'].create({
            'name': 'Company Holder 2',
            'is_company': False,
        })

        cls.share_class_ord = cls.env['equity.security.class'].create({'name': 'ORD'})
        cls.share_class_seed = cls.env['equity.security.class'].create({'name': 'Seed'})
        cls.share_class_a = cls.env['equity.security.class'].create({'name': 'Class A', 'share_votes': 2})
        cls.share_class_b = cls.env['equity.security.class'].create({'name': 'Class B'})
        cls.option_class_1 = cls.env['equity.security.class'].create({'name': 'Option pool 1', 'class_type': 'options'})
        cls.option_class_2 = cls.env['equity.security.class'].create({'name': 'Option pool 2', 'class_type': 'options'})

        cls.env['equity.valuation'].create([{
            'event': 'transaction',
            'partner_id': cls.company.id,
            'date': '2010-01-01',
            'valuation': 1000,
        }])
