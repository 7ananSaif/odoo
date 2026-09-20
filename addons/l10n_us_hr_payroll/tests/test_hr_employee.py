# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHrEmployee(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_us, self.company_be = self.env['res.company'].create([
            {
                'name': 'US Company',
                'country_id': self.env.ref('base.us').id
            },
            {
                'name': 'BE Company',
                'country_id': self.env.ref('base.be').id
            }
        ])
        self.env.user.company_ids |= self.company_us
        self.env.user.company_id = self.company_us  # hr.version retrieves this partner in _get_default_address_id()

    def test_company_context(self):
        # This test is testing a hr_employee/hr_version feature, but must be in l10n_us as we need the ssnid constraint.
        # We ensure that the company is passed in the context to the version by creating a belgian employee from the
        # US company with an invalid US SNN. It must not raise a ValidationError.
        be1, be2, us1, be3, us2 = self.env['hr.employee'].with_company(self.company_us).create([
            {'name': 'Belgian Employee 1', 'ssnid': '1', 'company_id': self.company_be.id},
            {'name': 'Belgian Employee 2', 'ssnid': '2', 'company_id': self.company_be.id},
            {'name': 'US Employee 1', 'ssnid': '111111111', 'company_id': self.company_us.id},
            {'name': 'Belgian Employee 3', 'ssnid': '3', 'company_id': self.company_be.id},
            {'name': 'US Employee 2', 'ssnid': '222222222', 'company_id': self.company_us.id},
        ])
        # We also test that the record are correctly re-ordered
        self.assertEqual(be1.ssnid, '1')
        self.assertEqual(be2.ssnid, '2')
        self.assertEqual(be3.ssnid, '3')
        self.assertEqual(us1.ssnid, '111111111')
        self.assertEqual(us2.ssnid, '222222222')
