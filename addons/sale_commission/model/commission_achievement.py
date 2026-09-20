# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _, api


class SaleCommissionAchievement(models.Model):
    _name = 'sale.commission.achievement'
    _description = 'Manual Commission Achievement'
    _order = 'id desc'

    add_user_id = fields.Many2one('sale.commission.plan.user', "Add to", domain=[('plan_id.active', '=', True)])
    reduce_user_id = fields.Many2one('sale.commission.plan.user', "Reduce From", domain=[('plan_id.active', '=', True)])
    achieved = fields.Monetary("Achieved", currency_field='currency_id')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=False, default=lambda self: self.env.company)
    date = fields.Date("Date", default=fields.Date.today, required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    currency_rate = fields.Float(compute='_compute_currency_rate', store=True)
    note = fields.Char("Note")

    @api.depends('note')
    def _compute_display_name(self):
        for achievement in self:
            if achievement.note:
                achievement.display_name = _("Adjustment: %s", achievement.note)
            else:
                achievement.display_name = _("Adjustment %s", achievement.id)

    @api.depends('currency_id', 'date')
    def _compute_currency_rate(self):
        for achievement in self:
            achievement.currency_rate = self.env['res.currency']._get_conversion_rate(
                    from_currency=achievement.company_id.currency_id,
                    to_currency=achievement.currency_id,
                    company=achievement.company_id,
                    date=achievement.date or fields.Date.context_today(achievement),
            )
