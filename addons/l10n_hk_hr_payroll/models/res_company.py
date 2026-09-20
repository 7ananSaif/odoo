# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_hk_autopay = fields.Boolean(string="Payroll with HSBC Autopay payment")
    l10n_hk_autopay_type = fields.Selection(
        selection=[('h2h', "H2H Submission"), ('hsbcnet', "HSBCnet File Upload")],
        string="Autopay Type", help="H2H Submission: Directly submit to HSBC. HSBCnet File Upload: Upload file to HSBCnet.",
        default='h2h',
    )
    l10n_hk_autopay_partner_bank_id = fields.Many2one(string="Autopay Account", comodel_name='res.partner.bank', copy=False)
    l10n_hk_employer_name = fields.Char("Employer's Name shown on reports", compute='_compute_l10n_hk_employer_name', store=True, readonly=False)
    l10n_hk_employer_file_number = fields.Char("Employer's File Number")
    l10n_hk_manulife_mpf_scheme = fields.Char("Manulife MPF Scheme", size=8)
    l10n_hk_eoy_pay_month = fields.Selection(
        string="End of Year Payments Month",
        help="If set, End of Year Payments will be included in the payslip of the chose month.\nLeave empty to manually choose when to include it in each payslip.",
        selection=[
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December')
        ],
        default='12',
    )
    l10n_hk_use_mpf_offsetting = fields.Boolean(
        string="Use MPF Offsetting",
        help="If set, MPF Offsetting will be applied in case of Severance Pay/Long Service Pay for the pre-transition period.\nThis can be overridden for each payment.",
    )

    @api.constrains("l10n_hk_employer_file_number")
    def _check_l10n_hk_employer_file_number(self):
        for company in self:
            if not company.l10n_hk_employer_file_number:
                continue
            file_number = company.l10n_hk_employer_file_number.strip()
            if len(file_number) != 12 or file_number[3] != '-':
                raise UserError(company.env._("The Employer's File Number must be in the format of XXX-XXXXXXXX."))

    @api.constrains("l10n_hk_manulife_mpf_scheme")
    def _check_l10n_hk_manulife_mpf_scheme(self):
        for company in self:
            if company.l10n_hk_manulife_mpf_scheme and len(company.l10n_hk_manulife_mpf_scheme) != 8:
                raise UserError(company.env._("The Manulife MPF Scheme must be 8 characters long."))

    @api.depends("name")
    def _compute_l10n_hk_employer_name(self):
        for company in self:
            company.l10n_hk_employer_name = company.l10n_hk_employer_name or company.name
