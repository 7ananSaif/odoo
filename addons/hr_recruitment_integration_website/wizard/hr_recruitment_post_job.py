# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning
from odoo.tools.mail import is_html_empty


class HrRecruitmentPostJobWizard(models.TransientModel):
    _inherit = 'hr.recruitment.post.job.wizard'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        job = self.env['hr.job'].browse(res.get('job_id'))
        if not job:
            return res
        if 'job_apply_url' in fields:
            res['job_apply_url'] = job.full_url
        return res

    apply_method = fields.Selection(
        selection_add=[
            ('redirect', 'Redirect to company\'s website'),
        ], default='redirect')
    job_apply_url = fields.Char('Job url', compute="_compute_job_apply_url", store=True, readonly=False)
    # required are dropped to permit the user to generate the post without filling the fields
    post_html = fields.Html(required=False)
    platform_ids = fields.Many2many(required=False)
    campaign_start_date = fields.Date(required=False)
    job_is_published = fields.Boolean(related="job_id.is_published")

    @api.depends('job_id')
    def _compute_post_html(self):
        super()._compute_post_html()
        post_job_wizards_with_job = self.filtered(lambda job_wizard: job_wizard.job_id)
        for post_job_wizard in post_job_wizards_with_job:
            post_job_wizard.post_html = post_job_wizard.job_id._get_plain_text_description()

    @api.depends('job_id')
    def _compute_job_apply_url(self):
        for post_job_wizard in self:
            post_job_wizard.job_apply_url = post_job_wizard.job_id.full_url if post_job_wizard.job_id else False

    def _get_apply_vector(self):
        self.ensure_one()
        if self.apply_method == 'redirect':
            return self.job_apply_url
        return super()._get_apply_vector()

    def _check_fields_before_posting(self, error_msg=""):
        if is_html_empty(self.post_html):
            error_msg += _('Description is required.\n')
        if not self.platform_ids:
            error_msg += _('At least one job board must be selected.\n')
        if self.apply_method == 'redirect' and not self.job_apply_url:
            error_msg += _('URL is required if the apply method is \'Redirect to company\'s website\'.\n')
        if not self.campaign_start_date:
            error_msg +=_('Campaign Start Date is required.\n')
        return super()._check_fields_before_posting(error_msg)

    def action_post_job(self):
        res = super().action_post_job()
        if self.apply_method == 'redirect' and not self.job_id.is_published:
            self.job_id.is_published = True
        return res

    def action_generate_post(self, warning=True):
        self.ensure_one()
        if self.post_html and warning:
            additional_ctx = {
                'active_id': self.id,
                'from_global_view': self.env.context.get('from_global_view', False),
            }
            raise RedirectWarning(
                message=_('The Job Description will be replaced with the generated one, do you want to continue?'),
                action=self.env.ref(
                    'hr_recruitment_integration_website.hr_recruitment_post_job_wizard_action_regenerate_post').id,
                button_text=_('Generate'),
                additional_context=additional_ctx,
            )
        self.post_html = self.job_id._generate_post()
        view_id = False
        if self.env.context.get('from_global_view'):
            view_id = self.env.ref('hr_recruitment_integration_base.hr_recruitment_post_job_wizard_view_job_selectable_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publish on a Job Board'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'context': {'active_model': self._name},
            'target': 'new',
        }
