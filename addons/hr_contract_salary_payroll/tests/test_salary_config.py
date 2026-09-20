# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase, freeze_time
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSalaryConfig(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.contract_template = cls.env['hr.version'].create([{
            'name': 'Contract Template',
            'wage': 1000,
        }])

        cls.job = cls.env['hr.job'].create([{
            'name': 'Job',
            'contract_template_id': cls.contract_template.id,
        }])

        cls.applicant = cls.env['hr.applicant'].create([{
            'partner_name': 'From Applicant',
            'email_from': 'from.applicant@odoo.com',
            'job_id': cls.job.id,
        }])

        cls.applicant.action_generate_offer()
        cls.offer_from_applicant = cls.applicant.salary_offer_ids[0]

    def test_future_contract(self):
        """
        When using the salary config for an offer whose contract start date is in the future,
        the payslip created to simulate the gross, net, etc. in the salary config should have
        its period in the future too. Otherwise, an error would be raised because the payslip
        is outside the contract period.

        In this tour, we only check if the div with the salary package résumé exists.
        If the error is raised, this div won't exist and the test will fail as it is supposed to.
        """
        with freeze_time('2025-01-01'):
            self.offer_from_applicant.contract_start_date = '2025-06-01'
            self.start_tour(self.offer_from_applicant.url, 'hr_contract_salary_payroll_tour', login='admin')
