# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date


class HrPayrollIndex(models.TransientModel):
    _name = 'hr.payroll.index'
    _description = 'Index contracts'

    percentage = fields.Float("Percentage")
    description = fields.Char(
        "Description", compute='_compute_description', store=True, readonly=False,
        help="Will be used as the message specifying why the wage on the contract has been modified")
    employee_ids = fields.Many2many('hr.employee', string="Employees")
    version_ids = fields.Many2many('hr.version', compute='_compute_version_ids', store=True, readonly=False, string="Employee records")
    affected_version_ids = fields.Many2many('hr.version', compute='_compute_affected_version_ids')
    informative_message = fields.Html(compute='_compute_informative_message')

    @api.depends('employee_ids')
    def _compute_version_ids(self):
        for wizard in self:
            wizard.version_ids = wizard.employee_ids.current_version_id

    @api.depends('version_ids')
    def _compute_affected_version_ids(self):
        for wizard in self:
            version_ids_by_employee = wizard.version_ids.grouped('employee_id')
            affected_versions = self.env['hr.version']
            for employee_id, version_ids in version_ids_by_employee.items():
                version_ids_by_contract_date = version_ids.grouped(lambda v: (v.contract_date_start, v.contract_date_end))
                for (date_start, date_end), contract_version_ids in version_ids_by_contract_date.items():
                    # Get all posterior versions related to the same contract
                    min_date_version = min(contract_version_ids.mapped('date_version'))
                    contract_version_ids |= employee_id.version_ids.filtered(
                        lambda v: v.date_version >= min_date_version and v.contract_date_start == date_start
                            and v.contract_date_end == date_end
                    )
                    affected_versions |= contract_version_ids
            wizard.affected_version_ids = affected_versions

    @api.depends('affected_version_ids')
    def _compute_informative_message(self):
        for wizard in self:
            wizard.informative_message = self.env._("<b>The following employee records will be modified:</b><br>") + "<br>".join(
                f"&nbsp;&nbsp;- {affected_version.display_name}" for affected_version in wizard.affected_version_ids.sorted('date_version')
            )

    @api.depends('percentage')
    def _compute_description(self):
        for wizard in self:
            wizard.description = self.env._(
                'Wage indexed by %(percentage).2f%% on %(date)s',
                percentage=self.percentage * 100,
                date=format_date(self.env, fields.Date.today()),
            )

    def action_confirm(self):
        self.ensure_one()

        if not self.percentage:
            return
        if self.percentage < 0:
            raise UserError(self.env._('Cannot index a wage with a null or negative percentage.'))

        version_ids_by_employee_id = self.affected_version_ids.grouped('employee_id')
        for employee_id, employee_version_ids in version_ids_by_employee_id.items():
            wage_field = employee_version_ids[0]._get_contract_wage_field()
            version_ids_by_wage = employee_version_ids.grouped(
                lambda v: v[wage_field]
            )
            modified_versions = self.env['hr.version']
            for wage, version_ids in version_ids_by_wage.items():
                version_ids.write({
                    wage_field: wage * (1 + self.percentage)
                })
                modified_versions |= version_ids

            message_body = self.description + Markup(self.env._("<br><b>Modified on Versions:</b><br>"))
            for v in modified_versions.sorted('date_version'):
                message_body += Markup("&nbsp;&nbsp;&nbsp;&nbsp;<b>- %s</b><br>" % v.display_name)

            employee_id.with_context(mail_post_autofollow_author_skip=True).message_post(
                body=message_body,
                message_type="comment",
                subtype_xmlid="mail.mt_note"
            )
