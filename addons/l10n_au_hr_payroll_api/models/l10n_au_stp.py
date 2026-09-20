# Part of Odoo. See LICENSE file for full copyright and licensing details.

from base64 import b64decode
import logging
from hashlib import sha256
from markupsafe import Markup

from odoo import models, fields, _, api
from odoo.exceptions import ValidationError, AccessError, UserError

_logger = logging.getLogger(__name__)


class L10n_AuSTP(models.Model):
    _inherit = "l10n_au.stp"

    ato_status = fields.Selection(
        [("draft", "Draft"), ("sent", "Submitted"), ("ato_ack", "ATO Pending"), ("accepted", "Accepted"), ("failed", "Failed")],
        string="ATO Status",
        default="draft",
        readonly=True,
        tracking=True,
    )
    message_id = fields.Char("API Message ID", readonly=True)

    @api.ondelete(at_uninstall=True)
    def _unlink_stp_records(self):
        if self.filtered(lambda r: r.ato_status in ["sent", "ato_ack", "accepted"]):
            raise UserError(_("You cannot delete STP records that have been submitted to the ATO."))

    def update_status(self, catch_errors=False):
        if not self:
            # Update all sent records
            stp_records = self.search([
                ("ato_status", "in", ["sent", "ato_ack"])
            ])
        else:
            stp_records = self

        companies = stp_records.mapped("company_id")
        for company in companies:
            if not (iap_proxy := company._l10n_au_payroll_get_proxy_user(catch_errors=catch_errors)):
                _logger.warning("No payroll proxy user found for company %s", company.name)
                continue

            company_stp_records = stp_records.filtered(lambda x: x.company_id == company)
            if not company_stp_records:
                continue

            response = iap_proxy._l10n_au_payroll_request(
                "/superchoice/payrollReportingResult",
                {
                    "message_ids": company_stp_records.mapped("message_id"),
                },
            )
            for record in stp_records:
                if response[record.message_id]["status"] == "failed":
                    # Handle Case where the error is waiting ATO Validation probably will be a different error code
                    if response[record.message_id]["error"]["code"] == "stp_validation_error":
                        record.ato_status = "failed"
                        _logger.error("Error in submission %s: %s", record.message_id, response[record.message_id]["error"]["message"])
                        record.post_errors(response[record.message_id]["error"]["message"])
                else:
                    record.ato_status = response[record.message_id]["status"]

    def action_pre_submit(self):
        if self.state == "draft":
            self.xml_validation_state = 'normal'
            self.with_context(payroll_presubmit=True).action_generate_xml()
        iap_proxy = self.company_id._l10n_au_payroll_get_proxy_user()
        if not iap_proxy:
            raise ValidationError(_("Please register your payroll before submitting the report. "
                                    "You can register it at Configuration > Settings > Payroll > Register Payroll."))

        response = iap_proxy._l10n_au_payroll_request("/superchoice/authenticateCredential", {}, handle_errors=False)
        if "error" in response:
            raise AccessError(response["error"])

        _logger.info("Authentication Successful!")
        params = {
            "payevent_type": self.payevent_type,
            "submission_id": self.submission_id,
            "xml_file": b64decode(self.xml_file).decode("utf-8"),
        }
        if self.payevent_type == "update":
            iap_proxy._l10n_au_payroll_request("/superchoice/payrollReportingUpdatePreSubmission", params)
        else:
            iap_proxy._l10n_au_payroll_request("/superchoice/payrollReportingPreSubmission", params)
        if self.state == "draft":
            self.xml_file = False
            self.xml_filename = False
            self.xml_validation_state = "done"

    def submit(self):
        if self.xml_validation_state != "done":
            self.action_pre_submit()

        super().submit()

        content = b64decode(self.xml_file)
        document_hash = sha256(content).hexdigest()
        if self.message_id == document_hash:
            raise ValidationError(_("The document has already been submitted."))
        self.message_id = document_hash

        iap_proxy = self.company_id._l10n_au_payroll_get_proxy_user()
        if not iap_proxy:
            raise ValidationError(_("Please register your payroll before submitting the report. "
                                    "You can register it at Configuration > Settings > Payroll > Register Payroll."))
        params = {
            "payevent_type": self.payevent_type,
            "submission_id": self.message_id,
            "xml_file": content.decode("utf-8"),
        }

        if self.payevent_type == "update":
            response = iap_proxy._l10n_au_payroll_request("/superchoice/payrollReportingUpdate", params, handle_errors=False)
        else:
            response = iap_proxy._l10n_au_payroll_request("/superchoice/payrollReporting", params, handle_errors=False)

        if "error" in response:
            self.ato_status = "failed"
            self.post_errors(response["error"], reset=True)
        else:
            self.ato_status = "sent"

    def post_errors(self, error_message, reset=False):
        # Cannot raise the errors on a submission because Superchoice considers it as a
        # duplicated submission if an error occurs and if it is resubmitted with the same
        # ID after corrections.
        self.message_post(
            body=Markup("""
<h3>Error(s) in submission [{submission_id}]:</h3>
<div><strong>Please retry after correcting the following errors</strong></div><br/>
<div>{error_message}</div>
            """).format(submission_id=self.submission_id, error_message=error_message)
        )

        if reset:
            self.action_draft()
        else:
            self.activity_schedule(
                "l10n_au_hr_payroll_account.l10n_au_activity_submit_stp",
                user_id=self.company_id.l10n_au_stp_responsible_id.user_id.id,
                note=_("Requires resubmission due to failure."),
            )

    def action_draft(self):
        # Used to reset STP files if ATO submission fails
        if self.filtered(lambda r: r.state != "sent" or r.ato_status != "failed"):
            raise ValidationError(_("This action is only available for reports with failed submissions."))
        self.write({
            "state": "draft",
            "xml_file": False,
            "xml_filename": False,
            "xml_validation_state": "normal",
            "error_message": False,
            "submission_id": False,
            "ato_status": "draft",
        })
        self.activity_unlink("l10n_au_hr_payroll_account.l10n_au_activity_submit_stp")
        self.activity_schedule(
            "l10n_au_hr_payroll_account.l10n_au_activity_submit_stp",
            user_id=self.company_id.l10n_au_stp_responsible_id.user_id.id,
            note=_("Reset to draft by %s due to failure.", (self.env.user.name)),
        )
