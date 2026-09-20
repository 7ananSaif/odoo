# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from freezegun import freeze_time
from dateutil.relativedelta import relativedelta

from odoo.addons.mail.tests.common import mail_new_test_user

from odoo.tests import Form
from odoo.tests.common import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestLinkExpirationDate(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.offer_date = datetime.date(2022, 1, 14)
        cls.validity_period = 30
        cls.fail_text = 'This link is invalid. Please contact the HR Responsible to get a new one...'

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({'name': 'struct'})
        cls.job = cls.env['hr.job'].create({
            'name': 'Familiar job',
        })
        cls.simple_user = mail_new_test_user(
            cls.env,
            name='Nandor Relentless',
            login='Al Qolnidar',
            email='Nandor@odoo.com',
            groups='base.group_user',
        )
        cls.employee = cls.env['hr.employee'].create({'name': "Nandor", 'user_id': cls.simple_user.id})

        cls.offer_refusal_reason = cls.env['hr.contract.salary.offer.refusal.reason'].create({
            'name': "Salary too high",
        })

    def test_access_token_on_change(self):
        self.env['hr.version'].create({
            'name': "Contract",
            'wage': 6500,
            'structure_type_id': self.structure_type.id,
            'job_id': self.job.id,
        })
        applicant = self.env["hr.applicant"].create(
            {
                "partner_name": "Guillermo De La Cruz",
                "email_from": "Guillermo@example.com",
            }
        )
        job = self.env['hr.job'].create({'name': 'Edge Runner'})
        contract_template = self.env['hr.version'].create({
            'job_id': job.id,
            'name': "Template Maze Runner Contract",
            'wage': 6500,
        })
        offer = self.env["hr.contract.salary.offer"].create({
            "applicant_id": applicant.id,
            "contract_template_id": contract_template.id,
        })

        with Form(offer.browse().with_context(active_id=offer.id, default_contract_template_id=contract_template.id, default_applicant_id=applicant.id)) as offer_form:
            self.assertTrue(offer_form.access_token)

    def test_generate_offer_by_hr_user(self):
        """Test that HR & Recruitment user can generate salary offer for applicant"""
        hr_user = mail_new_test_user(
            self.env,
            name='HR Officer User',
            login='hr_officer_user',
            groups='hr.group_hr_user,hr_recruitment.group_hr_recruitment_user'
        )
        self.env['hr.version'].create({
            'name': "Contract Template",
            'final_yearly_costs': 6500,
            'job_id': self.job.id,
        })
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'Guillermo De La Cruz',
            'email_from': 'Guillermo@example.com',
        })
        applicant.with_user(hr_user).action_generate_offer()
        self.assertEqual(applicant.salary_offers_count, 1)

    def test_link_for_applicant(self):
        """
        Applicant should be able to access salary configurator before the link Expires.
        After the link expiration date, applicant should be redirected to the invalid link page.
        """
        # If there is no demo version templates, then creating a version as follows will be necessary.
        # Otherwise, the following version creation can be deleted.
        self.env['hr.version'].create({
            'name': "Contract Template",
            'wage': 6500,
            'structure_type_id': self.structure_type.id,
            'job_id': self.job.id,
        })
        applicant = self.env["hr.applicant"].create(
            {
                "partner_name": "Guillermo De La Cruz",
                "email_from": "Guillermo@example.com",
            }
        )

        with freeze_time(self.offer_date):
            applicant.action_generate_offer()
            offer = applicant.salary_offer_ids
            offer.offer_end_date = self.offer_date + relativedelta(days=30)
            url = f'/salary_package/simulation/offer/{offer.id}?token={offer.access_token}'
            res = self.url_open(url)
        self.assertTrue(self.fail_text not in str(res.content),
                        "The applicant should not be redirected to the invalid link page")

        with freeze_time(self.offer_date + relativedelta(days=self.validity_period + 1)):
            late_res = self.url_open(url)
        self.assertTrue(self.fail_text in str(late_res.content),
                        'The applicant should be redirected to the invalid link page')

    def test_link_for_employee(self):
        self.employee.version_id.write({
            'wage': 6500,
            'structure_type_id': self.structure_type.id,
            'job_id': self.job.id,
        })
        employee_version = self.employee.version_id

        with freeze_time(self.offer_date):
            employee_version.action_generate_offer()
            offer = employee_version.salary_offer_ids
            offer.offer_end_date = self.offer_date + relativedelta(days=30)
            url = f'/salary_package/simulation/offer/{offer.id}'
            self.authenticate(self.simple_user.login, self.simple_user.login)
            res = self.url_open(url)
        self.assertTrue(self.fail_text not in str(res.content),
                        "The Employee should not be redirected to the invalid link page")

        with freeze_time(self.offer_date + relativedelta(days=self.validity_period + 1)):
            self.authenticate(self.simple_user.login, self.simple_user.login)
            late_res = self.url_open(url)
        self.assertTrue(self.fail_text in str(late_res.content),
                        'The Employee should be redirected to the invalid link page')
