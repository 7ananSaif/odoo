from odoo import api, fields, models


class L10n_Be_ReportsISOCPrepaymentPayWizard(models.TransientModel):
    _name = 'l10n_be_reports.isoc.prepayment.pay.wizard'
    _inherit = ['qr.code.payment.wizard']
    _description = "Payment instructions for ISOC prepayment"

    profit_estimate = fields.Monetary(
        string="Profit Estimate",
        currency_field='currency_id',
        required=True,
        default=0,
    )
    corporate_tax_rate = fields.Selection(related='company_id.l10n_be_isoc_corporate_tax_rate', required=True, readonly=False)

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard.profit_estimate = wizard.amount_to_pay * (400 / int(wizard.corporate_tax_rate))

        return wizards

    @api.depends('profit_estimate', 'corporate_tax_rate')
    def _compute_amount_to_pay(self):
        for wizard in self:
            wizard.amount_to_pay = wizard.profit_estimate * int(wizard.corporate_tax_rate) * 0.01 * 0.25
            wizard.return_id.total_amount_to_pay = wizard.amount_to_pay

    def action_pay_later(self):
        self.return_id.total_amount_to_pay = self.amount_to_pay

    def action_mark_as_paid(self):
        self.return_id.total_amount_to_pay = self.amount_to_pay
        super().action_mark_as_paid()

        return {
            'type': 'ir.actions.client',
            'tag': 'action_return_refresh',
            'params': {
                'next_action': {'type': 'ir.actions.act_window_close'},
                'return_ids': self.return_id.ids,
            },
        }

    def _generate_communication(self):
        return self._be_company_vat_communication(self.company_id)

    def action_send_email_instructions(self):
        # OVERRIDES account.return.payment.wizard
        self.ensure_one()
        template = self.env.ref('l10n_be_reports.email_template_vai_payment_instructions', raise_if_not_found=False)
        return self.return_id.action_send_email_instructions(self, template)
