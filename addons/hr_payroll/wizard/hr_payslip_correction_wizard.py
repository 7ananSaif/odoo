# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.fields import Command, Domain
from odoo.tools.misc import format_date


class HrPayslipCorrectionWizard(models.TransientModel):
    _name = "hr.payslip.correction.wizard"
    _description = "Payslip Correction Wizard"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True,
                                   help="The employee for whom the payslip correction is being made.")
    payslip_id = fields.Many2one("hr.payslip", string="Payslip", required=True)
    payslip_ids = fields.Many2many("hr.payslip", string="Payslips", compute="_compute_payslip_ids")
    payslip_count = fields.Integer(string="Payslip Count", compute="_compute_payslip_ids")
    is_multi_payslip = fields.Boolean(string="Multiple Payslips", compute="_compute_payslip_ids")
    correction_choice = fields.Selection(
        selection=[
            ('single', 'Correct this payslip only'),
            ('multi', 'Correct all affected payslips'),
        ],
        string="Correction Choice",
        required=True,
        default='single',
        help="Choose whether to correct only the selected payslip or all payslips affected by the changes in this version.",
    )

    @api.depends("employee_id")
    def _compute_payslip_ids(self):
        for wizard in self:
            domain = Domain.AND([
                Domain('employee_id', '=', wizard.employee_id.id),
                Domain('state', 'in', ['validated', 'paid']),
                Domain.OR([
                    Domain('is_wrong_version', '=', True),
                    Domain('has_wrong_data', '=', True),
                ]),
                Domain('keep_wrong_version', '=', False),
                Domain('is_refund_payslip', '=', False),
                Domain('is_refunded', '=', False),
                Domain('is_corrected', '=', False),
            ])
            wizard.payslip_ids = wizard.env['hr.payslip'].search(domain=domain, order="date_from")
            wizard.payslip_count = len(wizard.payslip_ids)
            wizard.is_multi_payslip = wizard.payslip_count > 1

    def action_revert_payslips(self):
        self.ensure_one()
        if self.correction_choice == 'single':
            refunds = self.payslip_id._action_refund_payslips()
            self.env['hr.payslip.run'].create({
                'name': self.env._("%(employee)s Revert %(date)s",
                    employee=self.employee_id.name,
                    date=format_date(self.env, self.payslip_id.date_from, date_format="MMMM Y")),
                'slip_ids': [Command.link(refund.id) for refund in refunds],
            })
        else:
            refunds = self.payslip_ids._action_refund_payslips()
            self.env['hr.payslip.run'].create({
                'name': self.env._("%(employee)s Revert %(date_start)s - %(date_end)s",
                    employee=self.employee_id.name,
                    date_start=format_date(self.env, self.payslip_ids[0].date_from, date_format="MMMM Y"),
                    date_end=format_date(self.env, self.payslip_ids[-1].date_from, date_format="MMMM Y")),
                'slip_ids': [Command.link(refund.id) for refund in (refunds)],
            })
        return refunds._get_payslips_action()

    def action_correct_payslips(self):
        self.ensure_one()
        if self.correction_choice == 'single':
            refunds = self.payslip_id._action_refund_payslips()
            corrections = self.payslip_id._action_correct_payslips()
            self.env['hr.payslip.run'].create({
                'name': self.env._("%(employee)s Correction %(date)s",
                    employee=self.employee_id.name,
                    date=format_date(self.env, self.payslip_id.date_from, date_format="MMMM Y")),
                'slip_ids': [Command.link(refund.id) for refund in (refunds | corrections)],
            })
        else:
            refunds = self.payslip_ids._action_refund_payslips()
            corrections = self.payslip_ids._action_correct_payslips()
            self.env['hr.payslip.run'].create({
                'name': self.env._("%(employee)s Correction %(date_start)s - %(date_end)s",
                    employee=self.employee_id.name,
                    date_start=format_date(self.env, self.payslip_ids[0].date_from, date_format="MMMM Y"),
                    date_end=format_date(self.env, self.payslip_ids[-1].date_from, date_format="MMMM Y")),
                'slip_ids': [Command.link(refund.id) for refund in (refunds | corrections)],
            })
        return (refunds | corrections)._get_payslips_action()

    def action_show_related_payslips(self):
        return self.payslip_ids._get_payslips_action()
