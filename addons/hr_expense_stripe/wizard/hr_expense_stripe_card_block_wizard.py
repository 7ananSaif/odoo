from odoo import _, fields, models


class HrExpenseStripeCardBlockWizard(models.TransientModel):
    _name = 'hr.expense.stripe.card.block.wizard'
    _description = 'A wizard used to block a card'

    card_id = fields.Many2one(comodel_name='hr.expense.stripe.card', string="Card To Block")
    cancellation_reason = fields.Selection(
        string="Reason",
        selection=[
            ('lost', "Lost"),
            ('stolen', "Stolen"),
            ('none', "Other"),
        ],
        default='lost',
        required=True,
    )
    other_reason_text = fields.Char(
        string="Description",
    )

    def action_block_card(self):
        """ Block the card **permanently** """
        for wizard in self:
            if wizard.cancellation_reason not in {False, 'none'}:
                wizard.card_id._create_or_update_card(state='canceled', cancellation_reason=wizard.cancellation_reason)
            else:
                wizard.card_id._create_or_update_card(state='canceled')

            wizard.card_id.cancellation_reason = wizard.cancellation_reason
            if wizard.cancellation_reason == 'none':
                default_reason = _("No reason provided")
                reason_msg = _(
                    "The card was blocked for the following reason:\n%(reason)s",
                    reason=wizard.other_reason_text or default_reason
                )
                wizard.card_id.message_post(message_type='comment', body=reason_msg)
