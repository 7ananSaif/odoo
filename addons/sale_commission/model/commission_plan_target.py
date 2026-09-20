# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, models, fields


class SaleCommissionPlanTarget(models.Model):
    _name = 'sale.commission.plan.target'
    _description = 'Commission Plan Target'
    _order = 'id'

    plan_id = fields.Many2one('sale.commission.plan', ondelete='cascade', index='btree_not_null')
    name = fields.Char("Period", required=True, readonly=True)
    date_from = fields.Date("From", required=True, readonly=True, index=True)
    date_to = fields.Date("To", required=True, readonly=True, index=True)
    payment_date = fields.Date(compute='_compute_payment_date', store=True, readonly=False, index=True)
    amount = fields.Monetary("Target", default=0, required=True, currency_field='currency_id')
    payment_amount = fields.Monetary(compute='_compute_payment_amount', currency_field='currency_id', store=True,
                                     help="Sum of amounts paid on the same payment date")
    currency_id = fields.Many2one('res.currency', related='plan_id.currency_id')

    @api.depends('date_to')
    def _compute_payment_date(self):
        for target in self:
            if not target.payment_date:
                target.payment_date = target.date_to

    @api.depends('payment_date', 'amount', 'plan_id')
    def _compute_payment_amount(self):
        """ Recompute the sum of amounts of the records sharing the same payment_date
        """
        amount_per_payment_date = defaultdict(list)
        total_per_date = defaultdict(float)
        # We need to group all related targets
        for target in self.plan_id.target_ids:
            # plan_id is used to avoid mixing targets from different plans
            key = (target.plan_id, target.payment_date)
            amount_per_payment_date[key].append(target.id)
            total_per_date[key] += target.amount
        for keys, target_ids in amount_per_payment_date.items():
            targets = self.browse(target_ids)
            targets.payment_amount = total_per_date[keys]
