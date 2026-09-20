# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.model
    def _get_line_batch_key(self, line):
        # OVERRIDE to use the bank account defined on the line, if any.
        res = super()._get_line_batch_key(line)
        if line.employee_bank_account_id:
            res['partner_bank_id'] = line.employee_bank_account_id.id
        return res

    def _reconcile_payments(self, to_process, edit_mode=False):
        res = super()._reconcile_payments(to_process, edit_mode=edit_mode)
        if self.env.context.get('hr_payroll_payment_register'):
            for vals in to_process:
                payslip = vals['to_reconcile'].move_id.payslip_ids
                vals['payment'].message_post_with_source(
                    'mail.message_origin_link',
                    render_values={'self': vals['payment'], 'origin': payslip},
                    subtype_xmlid='mail.mt_note',
                )
                payslip.message_post(body=_("Payment done at %s", vals['payment']._get_html_link()))

                if all(line.currency_id.is_zero(line.amount_residual_currency) for line in payslip.move_id.line_ids):
                    payslip.write({
                        "state": "paid",
                        "paid_date": self.payment_date
                    })

        return res
