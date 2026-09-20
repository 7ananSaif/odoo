# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.tests import tagged, Form
from odoo.addons.l10n_au_hr_payroll_api.models.account_edi_proxy_user import AccountEdiProxyClientUser
from odoo.addons.l10n_au_hr_payroll_account.tests.test_superstream import TestPayrollSuperStream
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from .common import TestL10nAUPayrollAPICommon


@tagged("post_install_l10n", "post_install", "-at_install", "l10n_au_hr_payroll")
class TestPayrollSuperStreamApi(TestPayrollSuperStream, TestL10nAUPayrollAPICommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("au")
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("hr_payroll.group_hr_payroll_manager")
        cls.env["ir.config_parameter"].sudo().set_param("l10n_au_payroll_test_server_url", "http://127.0.0.1:8070")
        # Created as 'demo' and switched to 'test' so no api request is tiggered
        cls.proxy_user = cls.env['account_edi_proxy_client.user']._register_proxy_user(cls.company_data['company'], 'l10n_au_payroll', 'demo')
        cls.proxy_user.edi_mode = 'test'
        assert cls.company.l10n_au_payroll_mode == "test"

        outbound_pay_method_line = cls.journal_id.with_context(l10n_au_super_payment=True) \
            ._get_available_payment_method_lines('outbound') \
            .filtered(lambda x: x.code == 'ss_dd')
        inbound_pay_method_line = cls.journal_id.with_context(l10n_au_super_payment=True) \
            ._get_available_payment_method_lines('inbound') \
            .filtered(lambda x: x.code == 'ss_dd')
        (outbound_pay_method_line + inbound_pay_method_line).payment_account_id = cls.inbound_payment_method_line.payment_account_id

        cls.SuperFund = cls.env["l10n_au.super.fund"]
        cls.employee_1 = cls.employee
        cls.employee_1.write({
            "user_id": cls.env.user.id,
            'work_phone': '123456789',
        })
        cls.bank_journal = cls.journal_id

    def setUp(self):
        super().setUp()
        self._register_company()
        self.assertEqual(self.company.l10n_au_bms_id, "123456")

    def _create_fund(self):
        self.env["l10n_au.super.account"].sudo().search([]).unlink()
        self.SuperFund.search([]).unlink()

        with self.mock_create_active_funds():
            self.SuperFund._update_active_funds()

    def test_00_superfund_update(self):
        self._create_fund()
        funds = self.SuperFund.search([], order="id")
        self.assertEqual(len(funds), 2)
        self.assertTrue(all(fund.fund_type == "APRA" for fund in funds))
        self.assertTrue(all(fund.is_valid for fund in funds))
        self.assertRecordValues(funds[0].address_id, [
            {
                "name": "Client Services Team",
                "phone": "1800254180",
                "email": "aetclientservices@aetlimited.com.au",
            }
        ])

        with self.mock_update_active_funds():
            self.SuperFund._update_active_funds()

        funds = self.SuperFund.search([], order="id")
        self.assertEqual(len(funds), 3)
        self.assertTrue(all(fund.fund_type == "APRA" for fund in funds))
        # Second fund no longer valid
        self.assertListEqual([fund.is_valid for fund in funds], [True, False, True])
        # First fund updated
        self.assertRecordValues(funds[0].address_id, [
            {
                "name": "New Contact name",
                "phone": "11223344",
                "email": "aetclientservices@aetlimited.com.au",
            }
        ])

    def test_01_super_stream_api(self):
        self._create_fund()
        valid_fund = self.env["l10n_au.super.fund"].search([("is_valid", "=", True)], limit=1)
        self.employee.l10n_au_super_account_ids.unlink()
        self.employee.write({
            "l10n_au_super_account_ids": [(0, 0, {
                "fund_id": valid_fund.id,
                "member_nbr": "123456",
            })]
        })
        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        self.payslips.move_id._post(False)
        superstream = self.payslips._get_superstreams()

        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        with self.mock_super_requests():
            superstream.action_register_super_payment()
            superstream.update_payment_status()

    def test_04_super_resubmit_failed(self):
        self._create_fund()
        valid_fund = self.env["l10n_au.super.fund"].search([("is_valid", "=", True)], limit=1)
        self.employee.l10n_au_super_account_ids.unlink()
        self.employee.write({
            "l10n_au_super_account_ids": [(0, 0, {
                "fund_id": valid_fund.id,
                "member_nbr": "123456",
            })]
        })

        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        self.payslips.move_id._post(False)
        superstream = self.payslips._get_superstreams()
        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        with self.mock_super_requests(status="pending"):
            superstream.action_register_super_payment()
            superstream.update_payment_status()
            superstream.action_cancel(superstream)

        with self.mock_super_requests(status="cancel"):
            superstream.update_payment_status()

        action = superstream.action_resubmit_failed()
        duplicated = self.env["l10n_au.super.stream"].browse(action["res_id"])
        self.assertEqual(duplicated.payment_status, "draft")
        self.assertEqual(duplicated.source_payment_status, "PENDING")
        self.assertEqual(duplicated.amount_total, superstream.amount_total)
        self.assertNotEqual(duplicated.l10n_au_super_stream_lines, superstream.l10n_au_super_stream_lines)
        self.assertEqual(duplicated.l10n_au_super_stream_lines.payslip_id, superstream.l10n_au_super_stream_lines.payslip_id)
        self.assertTrue(all(state == "PENDING" for state in duplicated.l10n_au_super_stream_lines.mapped("dest_payment_status")))

    def test_05_super_stream_cancellation(self):
        self._create_fund()
        valid_fund = self.env["l10n_au.super.fund"].search([("is_valid", "=", True)], limit=1)
        self.employee.l10n_au_super_account_ids.unlink()
        self.employee.write({
            "l10n_au_super_account_ids": [(0, 0, {
                "fund_id": valid_fund.id,
                "member_nbr": "123456",
            })]
        })

        self.payslips.compute_sheet()
        self.payslips.action_payslip_done()
        self.payslips.move_id._post(False)
        superstream = self.payslips._get_superstreams()
        superstream.journal_id = self.journal_id
        superstream.action_confirm()
        with self.mock_super_requests():
            superstream.action_register_super_payment()

        def action_cancel_success(endpoint, params=None, handle_errors=True):
            if endpoint == "/superchoice/cancel_payment":
                return {
                    "success": True,
                    }
            elif endpoint == "/superchoice/get_payment_status":
                return {superstream.message_id: {
                    "paymentOverview": {
                        "paymentStatus": "EMPLOYER_PAYMENT",
                    },
                    "paymentTransaction": [
                        {
                            "transactionType": "SOURCE",
                            "australianBusinessNumber": "85658499097",
                            "paymentType": "DIRECTDEBIT",
                            "timeInUTC": 1746728809866,
                            "expectedPaymentAmount": {
                                "value": 721.05,
                                "currency": "AUD",
                            },
                            "paymentReference": "PC090525-028728123",
                            "paymentStatus": "PENDING",
                        }
                    ],
                }}

        with patch.object(AccountEdiProxyClientUser, "_l10n_au_payroll_request", side_effect=action_cancel_success):
            action = superstream.action_cancel()
            wizard = Form.from_action(self.env, action)
            wizard.l10n_au_cancel_type = "dd_success"
            wizard.save().action_cancel()
            self.assertEqual(superstream.payment_status, "pending_cancel")

        refund_payment = self.env["account.payment"].search([("memo", "=", superstream.name + " (Refund)")])
        self.assertEqual(refund_payment.payment_type, "inbound")
        self.assertEqual(refund_payment.amount, superstream.amount_total)
        self.assertEqual(refund_payment.state, "in_process")
