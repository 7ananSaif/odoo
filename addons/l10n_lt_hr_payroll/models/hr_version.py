from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_lt_benefits_in_kind = fields.Monetary(
        string="Benefits in Kind", groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="""The following payments are not considered as benefits in kind:

- small value (not exceeding EUR 200) prizes, non-monetary presents received from employer;
- compensation received from employer for health treatment when required by law;
- working clothes, shoes, equipment and other assets given by employer to use only for work functions;
- directly to educational institutions paid amounts for individual‘s education;
- benefit received by an employee when an employer pays for rail and road public transport tickets which are used to travel to and from the work;
- personal income tax, social security and compulsory health insurance contributions paid on behalf of an individual.

Benefit in kind is taxed as employment income.""")
    l10n_lt_time_limited = fields.Boolean(
        string="Signed time-limited work agreement", groups="hr_payroll.group_hr_payroll_user", tracking=True)
    l10n_lt_pension = fields.Boolean(
        string="Participate to pension accumulation system", groups="hr_payroll.group_hr_payroll_user", tracking=True,
        help="""Employees can participate in an additional pension accumulation system. Inclusion into the accumulation system is used as one of the most effective methods to induce people to accumulate for additional pension if they have not started yet. However, it is not a coercive mechanism because any employed person may refuse accumulation if she/he does not want or has some other priorities.""")
    l10n_lt_working_capacity = fields.Selection([
        ('0_25', 'Between 0-25%'),
        ('30_55', 'Between 30-55%'),
        ('60_100', 'Between 60-100%'),
    ], default='60_100', string="Working Capacity", groups="hr_payroll.group_hr_payroll_user", tracking=True)

    @api.model
    def _get_whitelist_fields_from_template(self):
        whitelisted_fields = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == "LT":
            whitelisted_fields += [
                "l10n_lt_benefits_in_kind",
                "l10n_lt_pension",
                "l10n_lt_time_limited",
            ]
        return whitelisted_fields
