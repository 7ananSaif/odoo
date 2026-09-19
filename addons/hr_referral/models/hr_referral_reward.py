# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrReferralReward(models.Model):
    _name = 'hr.referral.reward'
    _description = 'Reward for Referrals'
    _order = 'sequence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = "read"

    def _group_hr_referral_domain(self):
        group = self.env.ref('hr_referral.group_hr_recruitment_referral_user', raise_if_not_found=False)
        return [('all_group_ids', 'in', group.ids)] if group else []

    sequence = fields.Integer()
    active = fields.Boolean(default=True)
    name = fields.Char('Product Name', required=True)
    cost = fields.Integer('Cost', required=True, tracking=True)
    awarded_employees = fields.Integer(compute='_compute_awarded_employees')
    points_missing = fields.Integer(compute='_compute_points_missing')
    description = fields.Html(required=True)
    gift_manager_id = fields.Many2one('res.users', string='Gift Responsible', tracking=True,
        domain=_group_hr_referral_domain, help="User responsible of this gift.")
    gift_manager_image = fields.Binary("Gift Responsible Image", related="gift_manager_id.image_1024")
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, required=True)
    image = fields.Binary("Image",
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    is_gift_manager = fields.Boolean(compute="_compute_is_gift_manager", default=True)

    def _compute_awarded_employees(self):
        data = {hr_referral_reward.id: count for hr_referral_reward, count in self.env['hr.referral.points']._read_group(
            [('hr_referral_reward_id', 'in', self.ids)],
            ['hr_referral_reward_id'],
            ['__count'])}
        for item in self:
            item.awarded_employees = data.get(item.id, 0)

    def _compute_points_missing(self):
        read_group_res = self.env['hr.referral.points']._read_group([('ref_user_id', '=', self.env.user.id)], ['company_id'], ['points:sum'])
        available_points_company = {company.id: points_sum for company, points_sum in read_group_res}
        for item in self:
            item.points_missing = item.cost - available_points_company.get(item.company_id.id, 0)

    @api.depends_context('uid')
    def _compute_is_gift_manager(self):
        current_user = self.env.user
        is_manager = current_user.has_group('hr_referral.group_hr_referral_manager')
        for reward in self:
            reward.is_gift_manager = bool(is_manager or reward.gift_manager_id == current_user)

    def buy(self):
        current_user = self.env.user
        available_points = sum(self.env['hr.referral.points'].search([('ref_user_id', '=', current_user.id), ('company_id', '=', self.company_id.id)]).mapped('points'))

        if available_points < self.cost:
            raise UserError(_("You do not have enough points in this company to buy this product. In this company, you have %s points.", available_points))

        # Use sudo, employee has normaly not the right to create or write on points
        self.env['hr.referral.points'].sudo().create({
            'ref_user_id': current_user.id,
            'points': - self.cost,
            'hr_referral_reward_id': self.id,
            'company_id': self.company_id.id
        })
        if self.gift_manager_id:
            # log a next activity for today
            self.sudo().activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                summary=_('New gift awarded for %s', current_user.name),
                user_id=self.gift_manager_id.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }   

    def action_get_employee_awarded(self):
        points_ids = self.env['hr.referral.points'].search([('hr_referral_reward_id', 'in', self.ids)]).ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Awarded Employees'),
            "views": [[self.env.ref('hr_referral.view_hr_referral_gift_tree').id, "list"], [False, "form"]],
            'view_mode': 'list',
            'res_model': 'hr.referral.points',
            'domain': [('id', 'in', points_ids)]
        }

    @api.model_create_multi
    def create(self, vals_list):
        reward_responsible_group = self.env.ref('hr_referral.group_hr_referral_reward_responsible_user', raise_if_not_found=False)
        if not reward_responsible_group:
            return super().create(vals_list)
        users_to_write = []
        for vals in vals_list:
            if vals.get('gift_manager_id', False):
                users_to_write.append((4, vals['gift_manager_id']))
        if users_to_write:
            reward_responsible_group.sudo().write({'user_ids': users_to_write})
        return super().create(vals_list)

    def write(self, vals):
        old_responsibles = self.env['res.users']
        if 'gift_manager_id' in vals:
            old_responsibles = self.mapped('gift_manager_id')
            gift_manager = False
            if vals['gift_manager_id']:
                gift_manager = self.env['res.users'].browse(vals['gift_manager_id'])
                old_responsibles -= gift_manager
            reward_responsible_group = self.env.ref('hr_referral.group_hr_referral_reward_responsible_user', raise_if_not_found=False)
            if reward_responsible_group and gift_manager and not gift_manager.has_group('hr_referral.group_hr_referral_reward_responsible_user'):
                reward_responsible_group.sudo().write({'user_ids': [(4, vals['gift_manager_id'])]})
        res = super().write(vals)
        old_responsibles._clean_responsibles()
        return res

    def action_open_buy_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Confirmation'),
            'res_model': 'hr.referral.reward',
            'views': [[False, 'form']],
            'view_id': self.env.ref('hr_referral.hr_referral_view_form_reward_purchase_dialog').id,
            'target': 'new',
            'res_id': self.id,
            'context': {
                'dialog_size': 'medium'
            },
        }
