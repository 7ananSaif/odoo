from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'

    card_id = fields.One2many(comodel_name='hr.expense.stripe.card', inverse_name='payment_method_line_id', string='Expense Card')
    employee_id = fields.Many2one(related='card_id.employee_id', readonly=True)

    @api.ondelete(at_uninstall=False)
    def _cannot_unlink_if_card_active(self):
        for payment_method_line in self:
            if payment_method_line.card_id.state in {'active', 'inactive'}:
                raise ValidationError(_(
                    "You cannot delete a payment method line that is used by an active/paused card."
                ))
