# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged
from datetime import date
from freezegun import freeze_time


@tagged('post_install_l10n', 'post_install', '-at_install', 'swissdec_payroll')
class TestWhitelistFromTemplate(TransactionCase):

    @freeze_time("2024-01-01")
    def setUp(self):
        super().setUp()
        self.company_ch = self.env['res.company'].create({
            'name': 'CH Co',
            'country_id': self.env.ref('base.ch').id,
        })
        self.employee_ch = self.env['hr.employee'].create({
            'name': 'CH Employee',
            'company_id': self.company_ch.id,
            'contract_date_start': "2024-01-01",
            'structure_type_id': self.env.ref('l10n_ch_hr_payroll.structure_type_employee_ch').id
        })

        LocationUnit = self.env['l10n.ch.location.unit'].with_context(tracking_disable=True)
        self.location_unit_1 = LocationUnit.create({
            "company_id": self.company_ch.id,
            "partner_id": self.env['res.partner'].create({
                'name': 'Hauptsitz',
                'street': 'Bahnhofstrasse 1',
                'zip': '6003',
                'city': 'Luzern',
                'country_id': self.env.ref('base.ch').id,
            }).id,
            "bur_ree_number": "A92978109",
            "canton": 'LU',
            "dpi_number": '158.87.6',
            "municipality": '1061',
            "weekly_hours": 42,
            "weekly_lessons": 21,
        })

        self.avs_1 = self.env['l10n.ch.social.insurance'].create({
            'name': 'AVS 2021',
            'member_number': '7019.2',
            "company_id": self.company_ch.id,
            'insurance_code': '079.000',
            'age_start': 18,
            'age_stop_male': 65,
            'age_stop_female': 64,
            'avs_line_ids': [(0, 0, {
                'date_from': date(2021, 1, 1),
                'employer_rate': 5.3,
                'employee_rate': 5.3,
            })],
            'ac_line_ids': [(0, 0, {
                'date_from': date(2021, 1, 1),
                'employer_rate': 1.1,
                'employee_rate': 1.1,
                'employee_additional_rate': 0.5,
                'employer_additional_rate': 0.5,
            })],
            'l10n_ch_avs_rente_ids': [(0, 0, {
                'date_from': date(2021, 1, 1),
                'amount': 1400
            })],
            'l10n_ch_avs_ac_threshold_ids': [(0, 0, {
                'date_from': date(2021, 1, 1),
                'amount': 148200
            })],
            'l10n_ch_avs_acc_threshold_ids': [(0, 0, {
                'date_from': date(2021, 1, 1),
                'amount': 370500
            })]
        })
        self.laa_1 = self.env['l10n.ch.accident.insurance'].create({
            'name': "Backwork-Versicherungen",
            'customer_number': '12577.2',
            "company_id": self.company_ch.id,
            'contract_number': '125',
            'insurance_code': 'S1000',
            'laa_group_ids': [
                (0, 0, {
                    "name": "Backwork-Versicherungen Group A",
                    "group_unit": "A",
                    "line_ids": [(0, 0, {
                        "date_from": date(2021, 1, 1),
                        "date_to": False,
                        "threshold": 148200,
                        "occupational_male_rate": 0,
                        "occupational_female_rate": 0,
                        "non_occupational_male_rate": 1.6060,
                        "non_occupational_female_rate": 1.6060,
                        "employer_occupational_part": "0",
                        "employer_non_occupational_part": "0",
                    })],
                })
            ],
        })
        self.laa_group_A = self.laa_1.laa_group_ids[0].id
        self.lpp_0 = self.env['l10n.ch.lpp.insurance'].create({
            "name": 'Pensionskasse Oldsoft',
            "company_id": self.company_ch.id,
            "customer_number": '1099-8777.1',
            "contract_number": '4500-0',
            'insurance_code': 'L1200',
            "solutions_ids": [
                (0, 0, {
                    "name": "Production",
                    "code": "11"}),
                (0, 0, {
                    "name": "Vente",
                    "code": "21"}),
                (0, 0, {
                    "name": "Administration",
                    "code": "22"}),
                (0, 0, {
                    "name": "Cadre surobligatoire",
                    "code": "K2010"})],
            "fund_number": False,
        })

        self.caf_lu_1 = self.env['l10n.ch.compensation.fund'].create({
            "name": 'Spida',
            "company_id": self.company_ch.id,
            "member_number": '5676.3',
            "member_subnumber": '',
            "insurance_code": '079.000',
            "caf_line_ids": [(0, 0, {
                'date_from': date(2021, 1, 1),
                'date_to': False,
                'employee_rate': 0,
                'company_rate': 0,
            })],
        })

    @freeze_time("2024-01-01")
    def validate_payslip_issues_presence(self, payslip, expected_action_texts):
        # Compute payslip to generate issues
        payslip.compute_sheet()
        issues = payslip.issues

        self.assertTrue(issues, "No issues generated for the payslip.")

        issue_action_texts = [issue['action_text'] for issue in issues.values()]
        for action_text in expected_action_texts:
            self.assertIn(
                action_text, issue_action_texts,
                f"Issue with action_text '{action_text}' not found in payslip.issues."
            )

    @freeze_time("2024-01-01")
    def test_ch_warnings_action_text_presence(self):
        """Test the presence of action_text values in payslip.issues."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Warning Slip',
            'employee_id': self.employee_ch.id,
            'date_from': "2024-01-01",
            'date_to': "2024-01-31",
        })

        expected_action_texts = [
            'Employee Reference',
            'Gender',
            'Birthday',
            'Nationality (Country)',
            'Canton',
            'Lang',
            'Marital Status Start Date',
            'Private Zip',
            'Private City',
            'Job',
            'AVS/AC Insurance',
            'Family Compensation Fund',
            'LPP Insurance',
            'LAA Code',
            'Workplace',
            'Private Country',
        ]

        self.validate_payslip_issues_presence(payslip, expected_action_texts)

        self.employee_ch.write(
            {'registration_number': '1', "l10n_ch_job_type": "lowerCadre", 'structure_type_id': self.env.ref('l10n_ch_hr_payroll.structure_type_employee_ch').id, 'contract_date_start': date(2022, 1, 1), 'contract_date_end': date(2022, 3, 31), 'wage_type': "hourly", 'l10n_ch_has_hourly': True, "l10n_ch_contractual_13th_month_rate": 8.33, 'wage': 0, 'hourly_wage': 50.0, 'l10n_ch_lesson_wage': 50.0, 'l10n_ch_has_lesson': True, 'l10n_ch_location_unit_id': self.location_unit_1.id, 'l10n_ch_social_insurance_id': self.avs_1.id, 'l10n_ch_laa_group': self.laa_group_A, 'laa_solution_number': '1', 'l10n_ch_lpp_insurance_id': self.lpp_0.id, 'l10n_ch_compensation_fund_id': self.caf_lu_1.id, 'l10n_ch_thirteen_month': True, 'l10n_ch_yearly_holidays': 0, 'certificate': 'higherVocEducation', 'name': "Herz Monica", 'sex': 'female', 'company_id': self.company_ch.id, 'country_id': self.env.ref('base.ch').id, 'l10n_ch_sv_as_number': False, 'birthday': date(1976, 6, 30), 'marital': 'married', 'l10n_ch_marital_from': date(2001, 5, 25), 'private_street': 'Bahnhofstrasse 1', 'private_zip': '6020', 'private_city': 'Emmenbrücke', 'private_country_id': self.env.ref('base.ch').id, 'l10n_ch_municipality': 1024, 'l10n_ch_residence_category': False, 'l10n_ch_canton': 'LU', 'lang': 'en_US'},
        )
        expected_action_texts_2 = [
            'Job',
        ]

        self.validate_payslip_issues_presence(payslip, expected_action_texts_2)
