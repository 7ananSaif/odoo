from odoo import api, models, fields


class AccountReturnGenericPaymentWizard(models.TransientModel):
    _name = "account.return.payment.wizard"
    _description = "Returns Generic Payment Wizard"

    company_id = fields.Many2one(comodel_name='res.company', string="Company")
    partner_id = fields.Many2one(comodel_name='res.partner', related='partner_bank_id.partner_id')
    acc_number = fields.Char(string="IBAN", related='partner_bank_id.acc_number')
    partner_bank_id = fields.Many2one(comodel_name='res.partner.bank')
    communication = fields.Char(compute='_compute_communication')

    amount_to_pay = fields.Monetary(compute='_compute_amount_to_pay', store=True, readonly=False)
    is_recoverable = fields.Boolean(compute='_compute_is_recoverable', readonly=False)
    currency_id = fields.Many2one(comodel_name='res.currency', related='return_id.amount_to_pay_currency_id')
    return_id = fields.Many2one(comodel_name='account.return', required=True)

    def _generate_communication(self):
        return False

    @api.depends('return_id')
    def _compute_amount_to_pay(self):
        for wizard in self:
            wizard.amount_to_pay = wizard.return_id.total_amount_to_pay

    @api.depends('amount_to_pay')
    def _compute_is_recoverable(self):
        for wizard in self:
            result = wizard.currency_id.compare_amounts(wizard.amount_to_pay, 0)
            wizard.is_recoverable = result == -1 or result == 0

    @api.depends('company_id')
    def _compute_communication(self):
        for wizard in self:
            wizard.communication = wizard._generate_communication()

    def action_mark_as_paid(self):
        self.ensure_one()
        return self.return_id._action_finalize_payment()

    def action_send_email_instructions(self):
        self.ensure_one()
        template = self.env.ref('account_reports.email_template_generic_tax_instructions', raise_if_not_found=False)
        return self.return_id.action_send_email_instructions(self, template)
