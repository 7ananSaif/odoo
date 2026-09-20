from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountTransferModelLine(models.Model):
    _name = 'account.transfer.model.line'
    _description = "Account Transfer Model Line"
    _order = "sequence, id"

    transfer_model_id = fields.Many2one('account.transfer.model', string="Transfer Model", required=True, index=True, ondelete='cascade')
    account_id = fields.Many2one('account.account', string="Destination Account", domain="[('account_type', '!=', 'off_balance')]")
    percent = fields.Float(string="Percent", required=True, default=100, help="Percentage of the sum of lines from the origin accounts will be transferred to the destination account")
    sequence = fields.Integer("Sequence")

    _unique_account_by_transfer_model = models.Constraint(
        'UNIQUE(transfer_model_id, account_id)',
        "Only one account occurrence by transfer model",
    )

    @api.constrains('account_id')
    def _constrains_account_id(self):
        """Check that there is a destination account set on each transfer model line and that it is unique."""
        for record in self:
            if not record.account_id:
                raise ValidationError(_("A destination account must be set on each line."))
