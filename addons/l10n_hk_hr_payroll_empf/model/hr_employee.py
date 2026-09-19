# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ------------------
    # Fields declaration
    # ------------------

    l10n_hk_mpf_exempt = fields.Boolean(
        related='version_id.l10n_hk_mpf_exempt',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_registration_status = fields.Selection(
        related='version_id.l10n_hk_mpf_registration_status',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_contribution_start = fields.Selection(
        related="version_id.l10n_hk_mpf_contribution_start",
        groups="hr_payroll.group_hr_payroll_user",
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_scheme_id = fields.Many2one(
        related='version_id.l10n_hk_mpf_scheme_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('employer_account_number', '!=', False)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_payroll_group_id = fields.Many2one(
        related='version_id.l10n_hk_payroll_group_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_member_class_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_id',
        groups='hr_payroll.group_hr_payroll_user',
        domain="[('company_id', '=', company_id), ('scheme_id', '=', l10n_hk_mpf_scheme_id)]",
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_account_number = fields.Char(
        related='version_id.l10n_hk_mpf_account_number',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_staff_number = fields.Char(
        related='version_id.l10n_hk_staff_number',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_mpf_scheme_join_date = fields.Date(
        related='version_id.l10n_hk_mpf_scheme_join_date',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
        readonly=False,
    )
    l10n_hk_scheme_group_count = fields.Integer(
        related='version_id.l10n_hk_scheme_group_count',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_previous_employment_date = fields.Date(
        string="Previous Date Of Employment",
        help="Fill this information in case of intra_group transfer.",
        groups='hr.group_hr_user',
        tracking=True,
    )
    l10n_hk_visa_issue_date = fields.Date(
        string="Visa Issue Date",
        help="Fill this information for expatriate employees.",
        groups='hr.group_hr_user',
        tracking=True,
    )
    l10n_hk_member_class_ct_eevc_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_eevc_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_member_class_ct_ervc_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_ervc_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
    l10n_hk_member_class_ct_ervc2_id = fields.Many2one(
        related='version_id.l10n_hk_member_class_ct_ervc2_id',
        groups='hr_payroll.group_hr_payroll_user',
        inherited=True,
    )
