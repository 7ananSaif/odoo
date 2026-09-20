# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import fields, models, _


class HrReferralRewardReport(models.Model):
    _name = 'hr.referral.reward.report'
    _description = "Employee Referral Reward Report"
    _auto = False
    _rec_name = 'reward_id'
    _order = 'write_date desc'

    write_date = fields.Date(string='Last Update Date', readonly=True)
    cost = fields.Integer('Unit Cost', readonly=True)
    awarded_employee_id = fields.Many2one('res.users', 'Responsible', readonly=True)
    rewarded_employees = fields.Integer('Rewarded Employees', readonly=True)
    reward_id = fields.Many2one('hr.referral.reward', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        query = '''
            (SELECT
                r.id as id,
                r.id as reward_id,
                h.ref_user_id as awarded_employee_id,
                r.write_date as write_date,
                r.cost as cost,
                r.company_id,
                COUNT(h.ref_user_id) as rewarded_employees
            FROM
                hr_referral_reward r
                INNER JOIN hr_referral_points h ON h.hr_referral_reward_id = r.id
                GROUP BY h.ref_user_id, r.id
            )
        '''

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, query), (_('Reward Referral'),))
