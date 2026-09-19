# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta
from markupsafe import Markup

from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import groupby, itemgetter
from odoo.fields import Domain
from .l10n_au_super_stream_utils import employerDetails, contributionDetails

_logger = logging.getLogger(__name__)


class L10n_auSuperStream(models.Model):
    _inherit = "l10n_au.super.stream"

    message_id = fields.Char("API Message ID", readonly=True, copy=False)
    payment_status = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("EMPLOYER_PAYMENT", "Employer Pending"),
            ("FUND_PAYMENT", "Fund Pending"),
            ("PAYMENT_COMPLETE", "Success"),
            ("pending_cancel", "Pending Cancellation"),  # Intermediate state when requested Cancellation
            ("PAYMENT_CANCELLED", "Cancelled")],
        string="Payment Status",
        required=True,
        default="draft",
        readonly=True,
        copy=False,
        help="""
Payment status for the overall payment of the transaction\n
Employer Pending - Employer direct debit has been initiated by SuperChoice.
Fund Pending - Employer direct debit has successfully cleared and payment to super funds have been initiated.
Success - All fund payments have been completed. This is a final state - you do not need to keep polling.
Pending Cancellation - Intermediate state when a cancellation for payment has been requested.
Cancelled - If any payments have been dishonoured or requested to be stopped prior to completion. This is a final state - you do not need to keep polling.
"""
    )
    payment_ref = fields.Char("Direct Debit Payment Ref.", readonly=True, copy=False, tracking=True)
    source_payment_status = fields.Selection(
        selection=[
            ("PENDING", "Pending"),
            ("COMPLETED", "Success"),
            ("SOURCE_FAILED", "Source Failed"),
            ("SOURCE_CANCELLED", "Source Cancelled")
        ],
        string="Direct Debit Status",
        required=True,
        default="PENDING",
        readonly=True,
        tracking=True,
        copy=False,
        help="""
Payment status for the Employer's direct debit to the Clearing House.
Pending - Employer direct debit has been initiated by SuperChoice.
Success - Employer direct debit has successfully cleared.
Source Failed - Employer direct debit has been dishonoured. The employer will need to resubmit with adequate funds in the bank account or with updated bank details.
Source Cancelled - Employer has requested for the direct debit to be stopped. If SuperChoice have already debited the employer, the funds will be refunded back to the employer's account after Day 3
"""
    )
    to_be_replaced = fields.Boolean(
        "To be Replaced",
        compute="_compute_to_be_replaced",
    )
    days_funds_update = fields.Integer(compute="_compute_funds_update")

    def _compute_to_be_replaced(self):
        for record in self:
            record.to_be_replaced = bool(
                record.l10n_au_super_stream_lines.filtered(
                    lambda x: x.dest_payment_status
                    in ("DESTINATION_FAILED", "DESTINATION_CANCELLED")
                    and not x.replaced_line_id
                )
            )

    def _compute_funds_update(self):
        last_call = self.env.ref("l10n_au_hr_payroll_api.l10n_au_super_update_funds").lastcall or fields.Datetime.now() - timedelta(days=1)
        diff = fields.Datetime.now() - last_call
        self.days_funds_update = diff.days if diff else 0

    def action_update_funds(self):
        self.env.ref("l10n_au_hr_payroll_api.l10n_au_super_update_funds").method_direct_trigger()
        self._compute_funds_update()

    def _validate_with_superchoice(self):
        """ Validation checks with SuperChoice API before submitting the report """
        iap_proxy = self.company_id._l10n_au_payroll_get_proxy_user()
        if not iap_proxy:
            raise ValidationError(_("Please register your payroll before submitting the report. "
                                    "You can register it at Configuration > Settings > Payroll > Register Payroll."))

        response = iap_proxy._l10n_au_payroll_request(
            "/superchoice/validate_employer",
            {
                "data": {"employer": {"employerDetails": employerDetails(self)}}
            },
            handle_errors=False,
        )
        if "error" in response:
            raise ValidationError(_("Error Validating Employer Details:\n%s", response['error']))

        response = iap_proxy._l10n_au_payroll_request(
            "/superchoice/validate_fund",
            {
                "data": {"fundDetails": contributionDetails(self, members=False)["employer"]}
            },
            handle_errors=False,
        )
        if "error" in response:
            raise ValidationError(_("Error Validating Funds :\n%s", response['error']))

        response = iap_proxy._l10n_au_payroll_request(
            "/superchoice/contribution",
            {
                "data": {"contributionDetails": contributionDetails(self)},
            },
            handle_errors=False,
        )
        if "error" in response:
            raise ValidationError(response["error"])

    def _create_super_stream_file(self):
        super()._create_super_stream_file()
        # Validate contributions
        self._validate_with_superchoice()

    def action_open_payment(self):
        refunds = self.env["account.payment"].search([
            ("payment_type", "=", "inbound"),
            ("memo", "=", self.name + " (Refund)"),
        ])
        return (refunds + self.payment_id)._get_records_action()

    def action_register_super_payment(self):
        action = super().action_register_super_payment()
        # Once the payment has successfully been created, we can submit to SuperChoice
        iap_proxy = self.company_id._l10n_au_payroll_get_proxy_user()
        if not iap_proxy:
            raise ValidationError(_("Please register your payroll before submitting the report. "
                                    "You can register it at Configuration > Settings > Payroll > Register Payroll."))

        response = iap_proxy._l10n_au_payroll_request(
            "/superchoice/contribution", {
                "data": {"contributionDetails": contributionDetails(self)},
                "validate": False
            }
        )
        self.message_id = response["messageId"]
        self.payment_status = "EMPLOYER_PAYMENT"
        return action

    def action_check_cancelation_type(self):
        return {
            "name": _("Cancel Payment"),
            "view_mode": "form",
            "res_model": "l10n_au.superstream.cancel",
            "view_id": self.env.ref("l10n_au_hr_payroll_api.l10n_au_superstream_cancel_view_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
            "context": {
                "default_l10n_au_super_stream_id": self.id,
            },
        }

    def action_cancel(self, force_refund=False, force_cancel=False, request_cancellation=True):
        """ Cancel the selected SuperStream
            force_refund: Forces the creation of a refund payment even if the payment was not reconciled
            in Odoo.
        """
        self.update_payment_status()
        if self.payment_status not in ("EMPLOYER_PAYMENT", "FUND_PAYMENT"):
            raise ValidationError(_("The payment can only be cancelled if it is pending. Payment has not been processed yet."))

        # If the Direct debit Payment was successful, we need to make a refund payment.
        # Else, ask the user to confirm if the payment was made.
        if self.source_payment_status == "COMPLETED" or self.payment_id.state == "paid" or force_refund:
            # Payment was already made, so we need a refund payment
            pay_method_line = self.journal_id.with_context(l10n_au_super_payment=True) \
                ._get_available_payment_method_lines('inbound') \
                .filtered(lambda x: x.code == 'ss_dd')
            if not self._get_default_payment_account(pay_method_line):
                raise UserError(_(
                    "An Outstanding Reciepts Account for the payment method '%(payment_method)s' is required to allow reconciliation.\n"
                    "Unable to find a default 'Outstanding Reciepts Account'. \n"
                    "Please select one under Accounting > Configuration > Journals > '%(journal)s' > Incoming Payments",
                    payment_method=pay_method_line.name, journal=self.journal_id.name))

            clearing_house_partner = self.env.ref('l10n_au_hr_payroll_account.res_partner_clearing_house', raise_if_not_found=False)
            if not clearing_house_partner.property_account_payable_id:
                raise UserError(_("Please set the SuperStream Payable Account for company %s.", self.company_id.name))

            payment = self.env['account.payment'].create({
                'date': fields.Datetime.now(),
                'amount': self.amount_total,
                'payment_type': 'inbound',
                'partner_id': clearing_house_partner.id,
                'partner_type': 'supplier',
                'memo': self.name + " (Refund)",
                'journal_id': self.journal_id.id,
                'currency_id': self.currency_id.id,
                'payment_method_line_id': pay_method_line.id,
            })
            payment.action_post()
            payment_message = _("A refund payment (%s) has been created successfully!", payment._get_html_link())
        elif force_cancel:
            # Payment failed and requires cancellation
            self.payment_id.action_cancel()
            payment_message = _("The outgoing payment (%s) has been cancelled!", self.payment_id._get_html_link())
        else:
            return self.action_check_cancelation_type()

        # Should not request cancellation in case of failure, instead just cancel the payment
        if not request_cancellation:
            return

        iap_proxy = self.company_id._l10n_au_payroll_get_proxy_user()
        if not iap_proxy:
            raise ValidationError(_("Please register your payroll before submitting the report. "
                                    "You can register it at Configuration > Settings > Payroll > Register Payroll."))
        response = iap_proxy._l10n_au_payroll_request(
            "/superchoice/cancel_payment",
            {
                "transaction_id": self.message_id
            },
            handle_errors=False,
        )
        if "error" in response:
            raise ValidationError(response["error"])
        if "success" in response:
            self.payment_status = "pending_cancel"
            self.message_post(body=_(
                "Payment cancellation requested successfully %(line_break)s %(payment_message)s",
                line_break=Markup('<br/>\n'),
                payment_message=payment_message
                ), author_id=self.env.user.partner_id.id)

    def _get_failed_lines(self):
        """ Returns the SuperStream lines that have failed in the destination payment """
        return self.l10n_au_super_stream_lines.filtered(
            lambda x: x.dest_payment_status in ("DESTINATION_FAILED", "DESTINATION_CANCELLED") and not x.replaced_line_id
        )

    def update_payment_status(self):
        if not self:
            records_to_update = self.search([("state", "=", "done"), ("l10n_au_super_stream_lines.dest_payment_status", "=", "PENDING")])
        else:
            records_to_update = self

        for company, records in records_to_update.grouped(lambda x: x.company_id).items():
            if records.filtered(lambda x: x.state != "done"):
                raise ValidationError(_("The payment status can only be updated for SuperStream records "
                                        "that have been submitted."))

            iap_proxy = company._l10n_au_payroll_get_proxy_user()
            if not iap_proxy:
                raise ValidationError(_("Please register your payroll before submitting the report. "
                                        "You can register it at Configuration > Settings > Payroll > Register Payroll."))

            response = iap_proxy._l10n_au_payroll_request(
                "/superchoice/get_payment_status",
                {
                    "transaction_ids": records.mapped("message_id")
                },
                handle_errors=True,
            )
            for record in records:
                record_response = response.get(record.message_id, {})
                if "error" in record_response:
                    _logger.error(record_response["error"])
                    record.message_post(body=record_response["error"])
                else:
                    if not record_response["paymentTransaction"]:
                        return
                    if record.payment_status == 'pending_cancel' and record_response["paymentOverview"]["paymentStatus"] != "PAYMENT_CANCELLED":
                        # When payment is cancelled, the status will be updated to PAYMENT_CANCELLED after a while
                        # until then, we use the temporary pending_cancel status
                        continue
                    record.payment_status = record_response["paymentOverview"]["paymentStatus"]
                    transaction_messages = []
                    for ref, transactions in groupby(record_response["paymentTransaction"], key=itemgetter("paymentReference")):
                        # Get the first transaction
                        transaction = transactions[0]
                        # Payment from source to clearing house
                        domains = []
                        if transaction["transactionType"] == "SOURCE":
                            record.source_payment_status = transaction["paymentStatus"]
                            record.payment_ref = ref
                            continue
                        elif transaction["transactionType"] == "DESTINATION" and "usi" in transaction:
                            # Fund Payment can be matched using USI but optional for SMSF
                            domains.append([("payee_id.usi", "=", transaction["usi"])])
                        elif transaction["transactionType"] == "DESTINATION":
                            # SMSF Fund Payment can be matched using ABN
                            domains.append([("payee_id.abn", "=", transaction["australianBusinessNumber"])])
                        fund_lines = record.l10n_au_super_stream_lines.filtered_domain(Domain.OR(domains))
                        # Update and Log a message if payment status changes
                        if any(fund_line.dest_payment_status != transaction["paymentStatus"] for fund_line in fund_lines):
                            transaction_messages.append(_("Payment status for fund '%(fund_name)s' has been updated from '%(from_status)s' to '%(to_status)s'.%(line_break)s"
                                                          "%(b)sReference%(b_end)s: %(ref)s%(line_break)s"
                                                          "%(b)sExpected Payment Amount%(b_end)s: %(expected_amount)s%(line_break)s"
                                                          "%(b)sActual Payment Amount%(b_end)s: %(actual_amount)s%(line_break)s",
                                                          b=Markup("<b>"), b_end=Markup("</b>"),
                                                          line_break=Markup("<br/>"),
                                                          fund_name=fund_lines[0].payee_id.display_name,
                                                          from_status=fund_lines[0].dest_payment_status,
                                                          to_status=transaction["paymentStatus"], ref=ref,
                                                          expected_amount=f"{transaction['expectedPaymentAmount']['currency']} {transaction['expectedPaymentAmount']['value']}",
                                                          actual_amount=f"{transaction['actualPaymentAmount']['currency']} {transaction['actualPaymentAmount']['value']}"))
                            fund_lines.write({
                                "dest_payment_status": transaction["paymentStatus"],
                                "dest_payment_ref": ref
                            })
                    if transaction_messages:
                        record.message_post(body=Markup("<br/>").join(transaction_messages))
                    if record.payment_status == "PAYMENT_CANCELLED":
                        record.activity_unlink(["l10n_au_hr_payroll_account.l10n_au_activity_resubmit_super"])
                        record.activity_schedule(
                            "l10n_au_hr_payroll_account.l10n_au_activity_resubmit_super",
                            user_id=record.company_id.l10n_au_hr_super_responsible_id.user_id.id,
                            note=_("Payment has been successfully cancelled. Please proceed with the needed corrections and resubmit")
                        )
                    elif self._get_failed_lines():
                        record.activity_unlink(["l10n_au_hr_payroll_account.l10n_au_activity_resubmit_super"])
                        record.activity_schedule(
                            "l10n_au_hr_payroll_account.l10n_au_activity_resubmit_super",
                            user_id=record.company_id.l10n_au_hr_super_responsible_id.user_id.id,
                            note=_("Some of the fund payments may have failed. Please check the report and resubmit if needed.")
                        )

    def action_resubmit_failed(self):
        failed_lines = self._get_failed_lines()
        if not failed_lines:
            raise ValidationError(_("No failed transactions to resubmit."))
        for failed_line in failed_lines:
            failed_line.replaced_line_id = failed_line.copy().id
        duplicated = self.copy({"l10n_au_super_stream_lines": failed_lines.replaced_line_id})

        # Cancel the orignal payments
        if self.source_payment_status == "SOURCE_FAILED":
            self.action_cancel(force_cancel=True, request_cancellation=False)
        # TODO: Partial refund amount for fund failure

        self.message_post(body=_("Failed transactions are being resubmitted in a new SuperStream report: %s", duplicated._get_html_link()))
        return duplicated.get_formview_action()


class L10n_auSuperStreamLine(models.Model):
    _inherit = "l10n_au.super.stream.line"

    dest_payment_ref = fields.Char("Fund Payment Ref.", readonly=True, copy=False)
    dest_payment_status = fields.Selection(
        selection=[
            ("PENDING", "Pending"),
            ("COMPLETED", "Success"),
            ("DESTINATION_FAILED", "Destination Failed"),
            ("DESTINATION_CANCELLED", "Destination Cancelled"),
        ],
        string="Fund Payment Status",
        required=True,
        default="PENDING",
        readonly=True,
        copy=False,
        help="Payment status for the Clearing House's payment to the Super Fund"
    )
    replaced_line_id = fields.Many2one("l10n_au.super.stream.line", "Replaced Line", readonly=True, copy=False)
