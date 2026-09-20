# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleCommissionPlanTargetForecast(models.Model):
    _name = 'sale.commission.plan.target.forecast'
    _description = 'Commission Plan Target Forecast'
    _order = 'id'

    plan_id = fields.Many2one('sale.commission.plan', ondelete='cascade', index=True)
    target_id = fields.Many2one('sale.commission.plan.target', string="Period", required=True, ondelete='cascade',
                                domain="[('plan_id', '=', plan_id)]", index=True)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, index=True)
    team_id = fields.Many2one('crm.team', related='user_id.sale_team_id', depends=['user_id'], store=True)
    amount = fields.Monetary("Forecast", default=0, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='plan_id.currency_id')
    notes = fields.Text("Notes")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Do it after to take default in account
        existing_plan_user = dict(self.env['sale.commission.plan.user']._read_group(
            [('user_id', 'in', records.user_id.ids), ('plan_id', 'in', records.plan_id.ids)],
            groupby=['user_id'], aggregates=['plan_id:array_agg'],
        ))
        for record in records:
            if record.plan_id.id not in existing_plan_user.get(record.user_id, {}):
                raise ValidationError(_('You cannot create a forecast for an user that is not in the plan.'))

        return records
