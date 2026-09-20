# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class HrJob(models.Model):
    _inherit = 'hr.job'

    job_post_count = fields.Integer(
        compute='_compute_job_post_count', string='Number of Job Posts', groups="hr_recruitment.group_hr_recruitment_user")
    job_post_ids = fields.One2many('hr.job.post', 'job_id', string='Job Posts', groups="hr_recruitment.group_hr_recruitment_user")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True, groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    salary_min = fields.Monetary('Minimum Salary', currency_field='currency_id', groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    salary_max = fields.Monetary('Maximum Salary', currency_field='currency_id', groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    payment_interval = fields.Selection([
        ('hourly', 'Hour'),
        ('daily', 'Day'),
        ('weekly', 'Week'),
        ('biweekly', 'Bi-Week'),
        ('monthly', 'Month'),
        ('yearly', 'Year'),
    ], string='Salary Time Unit', default='monthly', required=True, groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    schedule_id = fields.Many2one('resource.calendar', string='Working Schedule', groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    date_from = fields.Date(help="Is set, update applicants availability once hired for that specific mission.", groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")
    date_to = fields.Date(groups="hr.group_hr_user,hr_recruitment.group_hr_recruitment_user")

    @api.depends('job_post_ids')
    def _compute_job_post_count(self):
        for job in self:
            open_posts = job.job_post_ids.filtered(lambda post: post.status != 'deleted')
            job.job_post_count = len(open_posts)

    @api.onchange('salary_min', 'salary_max', 'payment_interval')
    def _onchange_salary(self):
        if self.salary_min > self.salary_max:
            self.salary_min, self.salary_max = self.salary_max, self.salary_min

    def write(self, vals):
        res = super().write(vals)

        # Update the availability on all hired applicants if the mission end date is changed
        if vals.get('date_to'):
            for job in self:
                hired_applicants = job.application_ids.filtered(lambda a: a.application_status == 'hired')
                for applicant in hired_applicants:
                    applicant.availability = job.date_to + relativedelta(days=1)
        return res

    def action_post_job(self):
        self.ensure_one()
        return {
            'name': _('Publish on a Job Board'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.recruitment.post.job.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_hr_job_post(self):
        self.ensure_one()
        action_dict = self.env.ref('hr_recruitment_integration_base.action_open_hr_job_post')._get_action_dict()
        action_dict.update({"domain": [('job_id', '=', self.id)]})
        return action_dict
