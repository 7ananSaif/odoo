# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    l10n_ch_pay_13th_month = fields.Boolean(
        string="Pay Thirteen Month")

    def _get_valid_version_ids(self, date_start=None, date_end=None, structure_id=None, company_id=None, employee_ids=None, schedule_pay=None):
        date_start = date_start or self.date_start
        date_end = date_end or self.date_end
        structure = self.env["hr.payroll.structure"].browse(structure_id) if structure_id else self.structure_id
        company = company_id or self.company_id.id

        if structure.code == "CHMONTHLYELM":
            all_contracts = self.env['l10n.ch.occupation'].search([])
            valid_contracts_sudo = all_contracts.sudo().filtered(lambda c:
                 c.date_start and
                 c.employee_id.company_id.id == company and
                 c.date_start <= date_end
                 and (not c.date_end or c.date_end >= date_start)
             )
            return valid_contracts_sudo.ids
        else:
            return super()._get_valid_version_ids(date_start, date_end, structure_id, company_id, employee_ids, schedule_pay)

    def generate_payslips(self, version_ids=None, employee_ids=None):
        self.ensure_one()
        if self.structure_id.code != "CHMONTHLYELM":
            return super().generate_payslips(version_ids, employee_ids)
        else:
            if employee_ids:
                all_contracts = self.env['l10n.ch.occupation'].search([('employee_id', 'in', employee_ids)])
                valid_contracts = all_contracts.filtered(lambda c:
                     c.date_start and
                     c.date_start <= self.date_end
                     and (not c.date_end or c.date_end >= self.date_start)
                 )
            elif version_ids:
                valid_contracts = self.env['hr.version'].browse(version_ids)
            else:
                raise UserError(self.env._("You must select employee(s) version(s) to generate payslip(s)."))
            Payslip = self.env['hr.payslip']
            default_values = Payslip.default_get(Payslip.fields_get())
            payslips_vals = []

            for contract in valid_contracts:
                values = {
                    **default_values,
                    'name': self.env._('New Payslip'),
                    'employee_id': contract.employee_id.id,
                    'payslip_run_id': self.id,
                    'company_id': self.company_id.id,
                    'date_from': self.date_start,
                    'date_to': self.date_end,
                    'version_id': contract.employee_id._get_version(max(contract.date_start, self.date_start)).id,
                    'struct_id': self.structure_id.id,
                }
                payslips_vals.append(values)
            self.slip_ids |= Payslip.with_context(tracking_disable=True).create(payslips_vals)
            self.slip_ids.compute_sheet()
            self.state = '01_ready'

            return 1
