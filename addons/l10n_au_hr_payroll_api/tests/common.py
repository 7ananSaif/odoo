# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from unittest.mock import patch

# from odoo.tests import Form
from odoo.addons.l10n_au_hr_payroll_api.models.account_edi_proxy_user import AccountEdiProxyClientUser
from odoo.addons.l10n_au_hr_payroll_api.models.res_company import ResCompany
from odoo.addons.l10n_au_hr_payroll_api.models.l10n_au_superstream import L10n_auSuperStream
from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


super_status = {
    "pending": {
        "payment_status": "EMPLOYER_PAYMENT",
        "source_payment_status": "PENDING",
        "dest_payment_status": "PENDING",
    },
    "complete": {
        "payment_status": "PAYMENT_COMPLETE",
        "source_payment_status": "COMPLETED",
        "dest_payment_status": "COMPLETED",
    },
    "cancel": {
        "payment_status": "PAYMENT_CANCELLED",
        "source_payment_status": "SOURCE_CANCELLED",
        "dest_payment_status": "DESTINATION_CANCELLED",
    },
}


class TestL10nAUPayrollAPICommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')

    def _register_company(self):
        self.env.company.l10n_au_payroll_mode = "test"

        def action_next(wizard):
            action = wizard.save().action_next()
            return Form.from_action(self.env, action)
        wizard = Form.from_action(self.env, self.company.action_view_payroll_onboarding())
        wizard.payroll_responsible_id = self.employee_1
        wizard = action_next(wizard)
        wizard.authorised = "yes"

        wizard = action_next(wizard)

        wizard = action_next(wizard)
        wizard.journal_id = self.bank_journal

        wizard = action_next(wizard)

        wizard.odoo_disclaimer_check = True
        wizard.superchoice_dda_check = True

        with self.mock_register_request():
            wizard.save().action_next()

    @contextmanager
    def mock_super_requests(self, status="complete"):
        def prepare_super_status_response(message_id):
            return {
                "identifier": {
                    "transactionId": {
                        "value": f"{message_id}"
                    },
                    "timeInUTC": 1683867649508
                },
                "paymentOverview": {
                    "source": {
                        "organisationName": "TEST EMPLOYER",
                        "australianBusinessNumber": "60295682905",
                        "employerPaymentDetails": {
                            "paymentType": "DIRECTDEBIT",
                            "directDebit": {
                                "directDebitPaymentAmount": {
                                    "value": 25.00,
                                    "currency": "AUD"
                                }
                            }
                        }
                    },
                    "targets": [
                        {
                            "fund": {
                                "usi": "20891605180001"
                            }
                        }
                    ],
                    "paymentStatus": super_status[status]["payment_status"],
                },
                "paymentTransaction": [
                    {
                        "transactionType": "DESTINATION",
                        "australianBusinessNumber": "20891605180",
                        "usi": "55387948703001",
                        "paymentType": "DIRECTCREDIT",
                        "timeInUTC": 1683125125859,
                        "expectedPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "actualPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "paymentReference": "PC010423-033710401",
                        "paymentStatus": super_status[status]["dest_payment_status"]
                    },
                    {
                        "transactionType": "DESTINATION",
                        "australianBusinessNumber": "20891605180",
                        "usi": "55387948703001",
                        "paymentType": "DIRECTCREDIT",
                        "timeInUTC": 1683038780169,
                        "expectedPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "actualPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "paymentReference": "PC010423-033710401",
                        "paymentStatus": super_status[status]["dest_payment_status"]
                    },
                    {
                        "transactionType": "SOURCE",
                        "australianBusinessNumber": "60295682905",
                        "paymentType": "DIRECTDEBIT",
                        "timeInUTC": 1683038058447,
                        "expectedPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "actualPaymentAmount": {
                            "value": 25.00,
                            "currency": "AUD"
                        },
                        "paymentReference": "PC010423-033710474",
                        "paymentStatus": super_status[status]["source_payment_status"]
                    },
                ]
            }

        def patched_l10n_au_payroll_request(endpoint, params=None, handle_errors=True):
            mocked_responses = {
                "/register": {"client_bms_id": "123456"},
                "/superchoice/authenticateCredential": {"success": True},
                "/superchoice/contribution": {"success": True, "messageId": "123456"},
                "/superchoice/get_payment_status": {message_id: prepare_super_status_response(message_id) for message_id in params.get("transaction_ids", [])},
                "/superchoice/cancel_payment": {"success": True},
                "/sync_audit_logs": {"success": True}
            }
            response = mocked_responses.get(endpoint)

            if response is None:
                raise ValidationError("Endpoint not found")

            return response

        def patched_validate_with_superchoice():
            pass

        with patch.object(AccountEdiProxyClientUser, "_l10n_au_payroll_request", side_effect=patched_l10n_au_payroll_request), \
             patch.object(L10n_auSuperStream, "_validate_with_superchoice", side_effect=patched_validate_with_superchoice):
            yield

    @contextmanager
    def mock_register_request(self):
        def patched_l10n_au_payroll_request(endpoint, params=None, handle_errors=True):
            mocked_responses = {
                "/register": {"client_bms_id": "123456"},
            }
            response = mocked_responses.get(endpoint, False)

            if not response:
                raise ValidationError(f"Endpoint '{endpoint}' not found")

            return response

        def patched_make_public_request(endpoint, params=None, handle_errors=True, timeout=False):
            mocked_responses = {
                "/superchoice/active_funds": {
                    "funds": []
                }
            }
            response = mocked_responses.get(endpoint, False)

            if not response:
                raise ValidationError("Endpoint not found")

            return response

        with patch.object(AccountEdiProxyClientUser, "_l10n_au_payroll_request", side_effect=patched_l10n_au_payroll_request), \
             patch.object(ResCompany, "_l10n_au_make_public_request", side_effect=patched_make_public_request):
            yield

    @contextmanager
    def mock_create_active_funds(self):
        def patched_make_public_request(endpoint, params=None, timeout=60):
            mocked_responses = {
                "/superchoice/active_funds": {
                    "funds": [
                        {
                            "usi": "55387948703001",
                            "fundName": "HERBERT REAL ESTATE PRIVATE SUPER FUND",
                            "productName": "Herbert Real Estate Private Super Fund",
                            "organisationName": "Herbert Real Estate Private Super Fund",
                            "australianBusinessNumber": "55387948703",
                            "scfi": "40f127aabf8665da87991b6958c744-00000",
                            "account": {
                                "accountName": "Australian Executor Trustees Ltd",
                                "bsb": "082395",
                                "accountNumber": "100012465",
                            },
                            "contactDetails": {
                                "name": "Client Services Team",
                                "phoneNumber": {"type": "LAND_LINE", "value": "1800254180"},
                                "email": {"value": "aetclientservices@aetlimited.com.au"},
                            },
                        },
                        {
                            "usi": "52330979326001",
                            "fundName": "MUIR FAMILY SUPERANNUATION FUND",
                            "productName": "Muir Family Superannuation Fund",
                            "organisationName": "Muir Family Superannuation Fund",
                            "australianBusinessNumber": "52330979326",
                            "scfi": "fbb136c1173ae10347bec4daac98645-0000",
                            "account": {
                                "accountName": "Muir Family Superannuation Fund",
                                "bsb": "182512",
                                "accountNumber": "962319075",
                            },
                            "contactDetails": {
                                "name": "Ian Ng",
                                "phoneNumber": {"type": "LAND_LINE", "value": "1800645227"},
                                "email": {"value": "diy.inbox@perpetual.com.au"},
                            },
                        },
                    ]
                },
            }
            response = mocked_responses.get(endpoint, False)

            if not response:
                raise ValidationError("Endpoint not found")

            return response

        with patch.object(ResCompany, "_l10n_au_make_public_request", side_effect=patched_make_public_request):
            yield

    @contextmanager
    def mock_update_active_funds(self):
        def patched_make_public_request(endpoint, params=None, timeout=60):
            return {
                    "funds": [
                        {
                            "usi": "55387948703001",
                            "fundName": "HERBERT REAL ESTATE PRIVATE SUPER FUND",
                            "productName": "Herbert Real Estate Private Super Fund",
                            "organisationName": "Herbert Real Estate Private Super Fund",
                            "australianBusinessNumber": "55387948703",
                            "scfi": "40f127aabf8665da87991b6958c744-00000",
                            "account": {
                                "accountName": "Australian Executor Trustees Ltd",
                                "bsb": "082395",
                                "accountNumber": "100012465",
                            },
                            "contactDetails": {
                                "name": "New Contact name",
                                "phoneNumber": {
                                    "type": "LAND_LINE",
                                    "value": "11223344",
                                },
                                "email": {
                                    "value": "aetclientservices@aetlimited.com.au"
                                },
                            },
                        },
                        {
                            "usi": "14895922426001",
                            "fundName": "STREITBERG PRIVATE SUPERANNUATION FUND",
                            "productName": "STREITBERG PRIVATE SUPERANNUATION FUND",
                            "organisationName": "STREITBERG PRIVATE SUPERANNUATION FUND",
                            "australianBusinessNumber": "14895922426",
                            "scfi": "ebbe1f5847e6828edf96e184924aa428-000",
                            "account": {
                                "accountName": "Australian Executor Trustees Ltd",
                                "bsb": "082395",
                                "accountNumber": "100031292",
                            },
                            "contactDetails": {
                                "name": "Client Services Team",
                                "phoneNumber": {
                                    "type": "LAND_LINE",
                                    "value": "1800254180",
                                },
                                "email": {
                                    "value": "aetclientservices@aetlimited.com.au"
                                },
                            },
                        },
                    ]
                }

        with patch.object(ResCompany, "_l10n_au_make_public_request", side_effect=patched_make_public_request):
            yield

    @contextmanager
    def mock_stp_requests(self):
        def patched_l10n_au_payroll_request(endpoint, params=None, handle_errors=True, timeout=False):
            mocked_responses = {
                "/register": {"client_bms_id": "123456"},
                "/superchoice/authenticateCredential": {"success": True},
                "/superchoice/payrollReportingUpdatePreSubmission": {"success": True},
                "/superchoice/payrollReportingPreSubmission": {"success": True},
                "/superchoice/payrollReportingUpdate": {"success": True},
                "/superchoice/payrollReporting": {"success": True},
                "/superchoice/payrollReportingResult": {
                    message_id: {"status": "accepted"}
                    for message_id in params.get("message_ids", [])
                }
            }
            response = mocked_responses.get(endpoint, False)

            if not response:
                raise ValidationError("Endpoint not found")

            return response

        with patch.object(AccountEdiProxyClientUser, "_l10n_au_payroll_request", side_effect=patched_l10n_au_payroll_request):
            yield

    @contextmanager
    def mock_audit_log_requests(self):
        def patched_l10n_au_payroll_request(endpoint, params=None, handle_errors=True):
            return {"success": True}

        with patch.object(AccountEdiProxyClientUser, "_l10n_au_payroll_request", side_effect=patched_l10n_au_payroll_request):
            yield
