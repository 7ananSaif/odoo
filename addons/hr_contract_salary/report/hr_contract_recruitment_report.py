# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import fields, models, _


class HrContractRecruitmentReport(models.Model):
    _name = "hr.contract.recruitment.report"
    _description = "Contract and Recruitment Analysis Report"
    _auto = False
    _rec_name = "offer_create_date"
    _order = "offer_create_date desc"

    offer_id = fields.Many2one("hr.contract.salary.offer", "Offer", readonly=True)
    applicant_id = fields.Many2one("hr.applicant", "Applicant", readonly=True)
    job_id = fields.Many2one("hr.job", "Job", readonly=True)
    offer_state = fields.Selection(
        [
            ("open", "In Progress"),
            ("half_signed", "Partially Signed"),
            ("full_signed", "Fully Signed"),
            ("expired", "Expired"),
            ("refused", "Refused"),
            ("cancelled", "Cancelled"),
        ],
        readonly=True,
    )
    offer_create_date = fields.Date("Offer Create Date", readonly=True)

    in_progress = fields.Integer(aggregator="sum", readonly=True)
    fully_signed = fields.Integer(aggregator="sum", readonly=True)
    partially_signed = fields.Integer(aggregator="sum", readonly=True)
    refused = fields.Integer(aggregator="sum", readonly=True)
    expired = fields.Integer(aggregator="sum", readonly=True)
    cancelled = fields.Integer(aggregator="sum", readonly=True)

    def action_open_applicant(self):
        self.ensure_one()
        return {
            "name": _("Applicants"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "hr.applicant",
            "res_id": self.applicant_id.id,
            "target": "current",
        }

    def _query(self, fields=""):
        return (
            """
            SELECT
            o.id as id,
            o.id as offer_id,
            o.state as offer_state,
            o.create_date as offer_create_date,
            o.employee_job_id as job_id,
            o.applicant_id as applicant_id,
            CASE WHEN o.state='open' THEN 1 ELSE 0 END as in_progress,
            CASE WHEN o.state='half_signed' THEN 1 ELSE 0 END as partially_signed,
            CASE WHEN o.state='full_signed' THEN 1 ELSE 0 END as fully_signed,
            CASE WHEN o.state='refused' THEN 1 ELSE 0 END as refused,
            CASE WHEN o.state='cancelled' THEN 1 ELSE 0 END as cancelled,
            CASE WHEN o.state='expired' THEN 1 ELSE 0 END as expired
            FROM hr_contract_salary_offer o
            %s
            """
            % fields
        )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query())
        )
