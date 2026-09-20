from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests.common import tagged, users


@tagged('mail_thread', 'mail_flow', 'mail_tools')
class TestOfferMailFeatures(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.job = cls.env['hr.job'].create({'name': 'Maze Runner'})
        cls.user_contract_manager = mail_new_test_user(
            cls.env,
            email='user_contract_manager@test.example.com',
            groups='hr.group_hr_manager,base.group_partner_manager',
            name='Contract Manager',
            notification_type='email',
            login='contract_manager',
            tz='Europe/Brussels',
        )
        cls.user_recruitment_manager = mail_new_test_user(
            cls.env,
            email='user_recruitment_manager@test.example.com',
            groups='hr_recruitment.group_hr_recruitment_manager,base.group_partner_manager',
            name='Contract Manager',
            notification_type='email',
            login='recruitment_manager',
            tz='Europe/Brussels',
        )

        cls.applicant = cls.env['hr.applicant'].create({
            'email_from': '"Mr Applicant" <applicant@test.example.com>',
            'partner_name': 'Amazing Applicant',
        })
        cls.applicant_nopartner = cls.env['hr.applicant'].create({
            'email_from': '"Mr Applicant NoPartner" <applicant.nopartner@test.example.com>',
            'partner_id': False,
            'partner_name': 'Amazing Applicant NoPartner',
        })
        auto_partner = cls.applicant_nopartner.partner_id
        cls.applicant_nopartner.partner_id = False
        auto_partner.unlink()
        cls.employee = cls.env['hr.employee'].create({
            'email': 'private@test.example.com',
            'name': 'Mr Employee',
            'work_email': 'hr.employee@test.example.com',
            'job_id': cls.job.id,
            'wage': 6500,
        })
        cls.contract_employee = cls.employee.version_id

        cls.contract_template = cls.env['hr.version'].create({
            'job_id': cls.job.id,
            'name': "Template Maze Runner Contract",
            'wage': 6500,
        })

        cls.salary_offers = cls.env['hr.contract.salary.offer'].create([
            {
                'applicant_id': cls.applicant.id,
                'contract_template_id': cls.contract_template.id,
            }, {
                'applicant_id': cls.applicant_nopartner.id,
                'contract_template_id': cls.contract_template.id,
            }, {
                'contract_template_id': cls.contract_template.id,
                'employee_version_id': cls.contract_employee.id,
                'employee_id': cls.contract_employee.employee_id.id,
            },
        ])

    def test_assert_initial_values(self):
        # work contact automatically created in create
        self.assertTrue(self.employee.work_contact_id)
        self.assertEqual(self.employee.work_contact_id.email, 'hr.employee@test.example.com')
        self.assertEqual(self.employee.work_contact_id.name, 'Mr Employee')
        # not sure where it comes from
        self.assertTrue(self.applicant.partner_id)
        self.assertEqual(self.applicant.partner_id.email, 'applicant@test.example.com')
        # forced
        self.assertFalse(self.applicant_nopartner.partner_id)

    def test_offer_default_recipients(self):
        """ Check default recipients, should try to contact always someone """
        offers = self.salary_offers.with_env(self.env)
        defaults = offers._message_get_default_recipients()
        expected_all = {
            offers[0].id: {
                'email_cc': '', 'email_to': '', 'partner_ids': self.applicant.partner_id.ids,
            },
            offers[1].id: {
                'email_cc': '',
                'email_to': '"Mr Applicant NoPartner" <applicant.nopartner@test.example.com>',
                'partner_ids': [],
            },
            offers[2].id: {
                'email_cc': '', 'email_to': '', 'partner_ids': self.employee.work_contact_id.ids,
            },
        }

        for offer, user in zip(offers, (
            self.user_recruitment_manager,
            self.user_recruitment_manager,
            self.user_contract_manager), strict=True
        ):
            # due to ACLs, we have to differentiate users (employee / applicant contracts)
            offer = offer.with_user(user)
            expected = expected_all.get(offer.id)
            with self.subTest(offer=offer, applicant_name=offer.applicant_id.partner_name, employee=offer.employee_id):
                self.assertEqual(defaults[offer.id], expected)

    def test_offer_suggested_recipients(self):
        """ Check suggested recipients, should include applicant, employee, ...
        when present in order to have people to propose. """
        offers = self.salary_offers.with_env(self.env)
        expected_all = [
            [
                {
                    'create_values': {},
                    'email': 'applicant@test.example.com',
                    'name': 'Amazing Applicant',
                    'partner_id': self.applicant.partner_id.id,
                },
            ], [
                {
                    'create_values': {},
                    'email': 'applicant.nopartner@test.example.com',
                    'name': 'Mr Applicant NoPartner',
                    'partner_id': False,
                },
            ], [
                {
                    'create_values': {},
                    'email': 'hr.employee@test.example.com',
                    'name': 'Mr Employee',
                    'partner_id': self.employee.work_contact_id.id,
                },
            ],
        ]

        for offer, user, expected in zip(offers, (
            self.user_recruitment_manager,
            self.user_recruitment_manager,
            self.user_contract_manager
        ), expected_all, strict=True):
            # due to ACLs, we have to differentiate users (employee / applicant contracts)
            offer = offer.with_user(user)
            with self.subTest(offer=offer, applicant_name=offer.applicant_id.partner_name, employee=offer.employee_id):
                suggested = offer._message_get_suggested_recipients()
                self.assertEqual(suggested, expected)

    def test_send_email(self):
        """ Test we succeed to send offers to people, based on found contact info """
        template_emp = self.env.ref('hr_contract_salary.mail_template_send_offer')
        template_app = self.env.ref('hr_contract_salary.mail_template_send_offer_applicant')
        for offer, exp_template, exp_notif in zip(
            self.salary_offers,
            (template_app, template_app, template_emp),
            (
                [{'partner': self.applicant.partner_id, 'type': 'email'}],
                [],  # specific, partner created during sending
                [{'partner': self.employee.work_contact_id, 'type': 'email'}],
            ),
            strict=True,
        ):
            with self.subTest(offer=offer, applicant_name=offer.applicant_id.partner_name, employee=offer.employee_id):
                action = offer.action_send_by_email()
                composer = self.env['mail.compose.message'].with_context(**action['context']).create({})
                self.assertEqual(composer.template_id, exp_template)
                with self.mock_mail_gateway():
                    _mails, message = composer._action_send_mail()
                # partner was created during sending mail process
                if offer == self.salary_offers[1]:
                    new_partner = self.env['res.partner'].search([('email_normalized', '=', 'applicant.nopartner@test.example.com')])
                    self.assertTrue(new_partner)
                    exp_notif = [{'partner': new_partner, 'type': 'email'}]

                self.assertMailNotifications(
                    message,
                    [{
                        'content': 'Congratulations',
                        'message_type': 'comment',
                        'notif': exp_notif,
                    }],
                )
