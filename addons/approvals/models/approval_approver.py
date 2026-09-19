# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models, fields, api
from odoo.exceptions import AccessError


class ApprovalApprover(models.Model):
    _name = 'approval.approver'
    _description = 'Approver'
    _order = 'sequence, id'

    _check_company_auto = True

    sequence = fields.Integer('Sequence', default=10)
    user_id = fields.Many2one('res.users', string="User", required=True, check_company=True,
        domain="""
            [
                ('share', '=', False),
                '|',
                    ('id', 'not in', existing_request_user_ids),
                    ('id', '=', user_id)
            ]
        """)
    existing_request_user_ids = fields.Many2many('res.users', compute='_compute_existing_request_user_ids')
    status = fields.Selection([
        ('new', 'New'),
        ('pending', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], string="Status", default="new", readonly=True)
    request_id = fields.Many2one('approval.request', string="Request",
        index='btree_not_null', ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        string='Company', related='request_id.company_id',
        store=True, readonly=True, index=True)
    required = fields.Boolean(default=False, readonly=True)
    category_approver = fields.Boolean(compute='_compute_category_approver')
    can_edit = fields.Boolean(compute='_compute_can_edit')
    can_edit_user_id = fields.Boolean(compute='_compute_can_edit', help="Simple users should not be able to remove themselves as approvers because they will lose access to the record if they misclick.")

    def write(self, vals):
        if 'request_id' in vals:
            request = self.env['approval.request'].browse(vals['request_id'])
            request.check_access('write')
            if self.request_id and self.request_id != request:
                raise AccessError(_("You cannot change approval request."))
        return super().write(vals)

    def action_approve(self):
        self.request_id.action_approve(self)

    def action_refuse(self):
        self.request_id.action_refuse(self)

    def _create_activity(self):
        for approver in self:
            approver.request_id.activity_schedule(
                'approvals.mail_activity_data_approval',
                user_id=approver.user_id.id)

    @api.depends('request_id.request_owner_id', 'request_id.approver_ids.user_id')
    def _compute_existing_request_user_ids(self):
        for approver in self:
            approver.existing_request_user_ids = \
                self.mapped('request_id.approver_ids.user_id')._origin \
              | self.request_id.request_owner_id._origin

    @api.depends('category_approver', 'user_id')
    def _compute_category_approver(self):
        for approval in self:
            approval.category_approver = approval.user_id in approval.request_id.category_id.approver_ids.user_id

    @api.depends_context('uid')
    @api.depends('user_id', 'category_approver')
    def _compute_can_edit(self):
        is_user = self.env.user.has_group('approvals.group_approval_user')
        for approval in self:
            approval.can_edit = is_user
            approval.can_edit_user_id = is_user or not approval.user_id

    _unique_request_user = models.Constraint(
        'UNIQUE(request_id, user_id)',
        "An approver with the same user already exists for this request.",
    )
