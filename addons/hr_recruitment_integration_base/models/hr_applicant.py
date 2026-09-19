from dateutil.relativedelta import relativedelta

from odoo import models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('date_closed'):
            for applicant in self.filtered('job_id.date_to'):
                applicant.availability = applicant.job_id.date_to + relativedelta(days=1)
        return res
