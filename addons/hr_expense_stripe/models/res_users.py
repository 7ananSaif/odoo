from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @property
    def SELF_READABLE_FIELDS(self):
        # The employee user can see their own cards
        return super().SELF_READABLE_FIELDS + ['stripe_card_ids']

    stripe_card_ids = fields.One2many(
        comodel_name='hr.expense.stripe.card',
        inverse_name='user_id',
        groups='base.group_user',
        check_company=True,
    )
