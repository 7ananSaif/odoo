# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrRecruitmentPostJobWizard(models.TransientModel):
    _name = 'hr.recruitment.post.job.wizard'
    _description = 'Post Job'
    _transient_max_count = 0
    _transient_max_hours = 24

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if self.env.context.get('active_model') == 'hr.job':
            res['job_id'] = self.env.context.get('active_id')
        return res

    campaign_start_date = fields.Date(string="Campaign Start Date", default=fields.Date.today(), required=True)
    campaign_end_date = fields.Date(
        string="Campaign End Date",
        help='The date when the campaign will end. If not set, '
        'the campaign will run indefinitely or to the maximum allowed by a platform.')
    job_id = fields.Many2one('hr.job', string="Job")
    industry_id = fields.Many2one(related="job_id.industry_id", readonly=False)
    job_apply_mail = fields.Char(string="Email", compute="_compute_job_apply_mail", store=True, readonly=False)
    apply_method = fields.Selection([
        ('email', 'Send an Email'),
    ], default='email', string="Apply Method")
    platform_ids = fields.Many2many('hr.recruitment.platform', string="Job Board", required=True)
    post_html = fields.Html(string="Description", required=True, compute="_compute_post_html", store=True,
        readonly=False)
    api_data = fields.Json(string="Data")
    post_ids = fields.Many2many('hr.job.post', 'job_id', string="Job Posts")
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(
        string="Mission date start",
        help="This will update the applicant's availability status once they are hired for this position.",
        related="job_id.date_from",
        readonly=False,
    )
    date_to = fields.Date(
        string="Mission date end",
        related="job_id.date_to",
        readonly=False,
    )

    @api.depends('job_id')
    def _compute_job_apply_mail(self):
        for post_job_wizard in self:
            job = post_job_wizard.job_id
            if job and job.alias_id.alias_full_name:
                post_job_wizard.job_apply_mail = job.alias_id.alias_full_name
            elif job and job.user_id and job.user_id.employee_id:
                post_job_wizard.job_apply_mail = job.user_id.work_email
            else:
                post_job_wizard.job_apply_mail = False

    @api.depends('job_id')
    def _compute_post_html(self):
        for post_job_wizard in self:
            if post_job_wizard.job_id:
                post_job_wizard.post_html = post_job_wizard.job_id.description
            else:
                post_job_wizard.post_html = False

    def _postpone_posts(self):
        self.ensure_one()
        posts_to_postpone = [
            {
                'job_id': self.job_id.id,
                'post_html': self.post_html,
                'platform_id': platform.id,
                'campaign_start_date': self.campaign_start_date,
                'campaign_end_date': self.campaign_end_date,
                'apply_method': self.apply_method,
                'apply_vector': self.job_apply_mail,
                'status': 'pending',
                'status_message': _(
                    'Campaign will start on %(start_date)s',
                    start_date=self.campaign_start_date
                ),
                'company_id': self.company_id.id,
            } for platform in self.platform_ids
        ]
        if self.post_ids:
            if any(post.status in ['success', 'warning'] for post in self.post_ids):
                raise UserError(_('Can\'t postpone posts that are already posted'))
            grouped_posts = {post.platform_id.id: post for post in self.post_ids}
            for platform, vals in zip(self.platform_ids, posts_to_postpone):
                grouped_posts[platform.id].sudo().write(vals)
            self.post_ids._log_post_modifications(mode=_('updated'))
        else:
            self.env['hr.job.post'].sudo().create(posts_to_postpone)

    def _get_apply_vector(self):
        self.ensure_one()
        if self.apply_method == 'email':
            return self.job_apply_mail
        return ''

    def _post_job(self, responses=None):
        self.ensure_one()

        if not responses:
            responses = {}

        posts = [
            {
                'job_id': self.job_id.id,
                'post_html': self.post_html,
                'platform_id': platform_id,
                'campaign_start_date': self.campaign_start_date,
                'campaign_end_date': self.campaign_end_date,
                'apply_method': self.apply_method,
                'apply_vector': self._get_apply_vector(),
                'status': responses[platform_id].get('status', 'failure'),
                'status_message': responses[platform_id].get('status_message', ''),
                'api_data': responses[platform_id].get('data', {}),
                'company_id': self.company_id.id
            } for platform_id in self.platform_ids.ids
        ]

        if self.post_ids:
            grouped_posts = {post.platform_id.id: post for post in self.post_ids}
            for platform, vals in zip(self.platform_ids, posts):
                grouped_posts[platform.id].write(vals)
            self.post_ids._log_post_modifications(mode=_('updated'))
        else:
            self.env['hr.job.post'].sudo().create(posts)

        if self.env.context.get('active_model') in ['hr.job', self._name]:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Job Posts'),
                'res_model': 'hr.job.post',
                'view_mode': 'kanban,list,form',
                'search_view_id': self.env.ref('hr_recruitment_integration_base.hr_job_post_view_kanban_search').id,
                'context': {"search_default_job_id": self.job_id.id},
            }
        return {'type': 'ir.actions.act_window_close'}

    def _check_fields_before_posting(self, error_msg=""):
        self.ensure_one()
        if self.campaign_end_date and self.campaign_start_date > self.campaign_end_date:
            error_msg += _('Campaign start date can\'t be after campaign end date.\n')
        if self.apply_method == "email" and not self.job_apply_mail:
            error_msg += _('Email is required if the apply method is \'Send an email\'.\n')
        if error_msg:
            raise UserError(error_msg)

    def action_post_job(self):
        self.ensure_one()
        self._check_fields_before_posting()
        if self.campaign_start_date > fields.Date.today():
            return self._postpone_posts()
        return self._post_job()
