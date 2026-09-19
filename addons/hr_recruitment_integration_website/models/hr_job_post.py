# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrJobPost(models.Model):
    _inherit = 'hr.job.post'

    apply_method = fields.Selection(
        selection_add=[('redirect', 'Redirect to Website')],
        ondelete={'redirect': 'cascade'},
    )

    @api.depends('job_id.full_url')
    def _compute_apply_vector(self):
        redirect_records = self.filtered(lambda r: r.apply_method == 'redirect')
        for record in redirect_records:
            record.apply_vector = record.job_id.full_url if record.job_id else False

        self -= redirect_records
        super()._compute_apply_vector()

    def _contact_point_to_vector(self):
        self.ensure_one()
        if self.apply_method == 'redirect':
            return 'job_apply_url'
        return super()._contact_point_to_vector()
