# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, Command

import logging


_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _compute_input_line_ids(self):
        """
        Set commission on the related input_line_ids of the payslip.
        """
        res = super()._compute_input_line_ids()
        payroll_commission_plan = self.env['sale.commission.plan'].search([('commission_payroll_input', '!=', 'False')])

        for (date_from, date_to, company_id), slips_sudo in self.sudo().grouped(lambda slip: (slip.date_from, slip.date_to, slip.company_id.id)).items():
            commissions = self.env['sale.commission.report'].sudo().search_fetch(
                [('user_id', 'in', slips_sudo.employee_id.user_id.ids), ('payment_date', '>=', date_from),
                 ('payment_date', '<=', date_to), ('company_id', '=', company_id),
                 ('plan_id', 'in', payroll_commission_plan.ids)],
                ['commission', 'user_id', 'currency_id']
            )
            commission_per_user = commissions.grouped('user_id')
            for slip_sudo in slips_sudo:
                user_commissions = commission_per_user.get(slip_sudo.employee_id.user_id, self.env['sale.commission.report'])
                for input, coms in user_commissions.grouped(lambda com: com.plan_id.commission_payroll_input).items():
                    if not input:
                        continue
                    total = 0
                    for commissions in coms:
                        total += commissions.currency_id._convert(
                            coms.commission, to_currency=slip_sudo.currency_id,
                            date=slip_sudo.date_to, company=slip_sudo.company_id
                        )
                    if total:
                        slip_sudo.input_line_ids = [Command.create({
                            'amount': total,
                            'input_type_id': input.id
                        })]
        return res
