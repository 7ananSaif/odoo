# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.addons.l10n_au_hr_payroll_account.tests.common import L10nPayrollAccountCommon
from .common import TestL10nAUPayrollAPICommon


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_au_hr_payroll")
class TestSingleTouchPayrollApi(L10nPayrollAccountCommon, TestL10nAUPayrollAPICommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['l10n_au.stp'].search([]).unlink()
        cls.env['ir.sequence'].create({
            'name': 'STP Sequence',
            'code': 'stp.transaction',
            'prefix': 'PAYEVENT0004',
            'padding': 10,
            'number_next': 1,
        })
        cls.company.l10n_au_bms_id = "ODOO_TEST_BMS_ID"
        cls.company.write({
                "vat": "85658499097",
                "email": "au_company@odoo.com",
                "phone": "123456789",
                "zip": "2000",
                'l10n_au_branch_code': '100',
        })
        cls.contract_1.date_end = False
        cls.env['ir.config_parameter'].sudo().set_param('l10n_au_payroll_iap.test_endpoint', 'http://127.0.0.1:8070')
        cls.proxy_user = cls.env['account_edi_proxy_client.user']._register_proxy_user(cls.company, 'l10n_au_payroll', 'demo')
        cls.proxy_user.edi_mode = 'test'
        assert cls.company.l10n_au_payroll_mode == 'test'
        cls.img_1x1_png = base64.b64decode(b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC')

    def setUp(self):
        self._register_company()

    def test_api_submit_event(self):
        payrun = self._prepare_payslip_run(self.employee_1 + self.employee_2)
        stp = self.env["l10n_au.stp"].search([("payslip_batch_id", "=", payrun.id)])
        stp.submit_date = date.today()
        with self.mock_stp_requests():
            self._submit_stp(stp)
            self.assertEqual(stp.state, "sent")
            stp.update_status()
        self.assertEqual(stp.ato_status, "accepted")

    @freeze_time("2024-03-31")
    def test_api_update_event(self):
        batch = self._prepare_payslip_run(self.employee_1 + self.employee_2)
        stp = self.env["l10n_au.stp"].search([("payslip_batch_id", "=", batch.id)])
        stp.submit_date = date.today()
        with self.mock_stp_requests():
            self._submit_stp(stp)
        stp_update = self.env["l10n_au.stp"].create(
            {
                "company_id": self.company.id,
                "payevent_type": "update",
                "l10n_au_stp_emp": [
                    (0, 0, {"employee_id": self.employee_1.id}),
                    (0, 0, {"employee_id": self.employee_2.id}),
                ],
            }
        )
        stp_update.submit_date = date.today()
        with self.mock_stp_requests():
            self._submit_stp(stp_update)

    def test_api_status_check(self):
        self._register_company()

        payrun = self._prepare_payslip_run(self.employee_1 + self.employee_2)
        stp = self.env["l10n_au.stp"].search([("payslip_batch_id", "=", payrun.id)])
        stp.submit_date = date.today()
        with self.mock_stp_requests():
            stp.action_pre_submit()
        self.assertEqual(stp.xml_validation_state, "done")
        self.assertEqual(stp.ato_status, "draft")
        with self.mock_stp_requests():
            self._submit_stp(stp)
        self.assertEqual(stp.ato_status, "sent")
        self.assertEqual(stp.state, "sent")

        with self.mock_stp_requests():
            stp.update_status()
        self.assertEqual(stp.ato_status, "accepted")
