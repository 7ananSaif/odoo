# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from ..models.account_return import PERIODS


class ResCompany(models.Model):
    _inherit = "res.company"

    totals_below_sections = fields.Boolean(
        compute='_compute_totals_below_sections', store=True,
        string='Add totals below sections',
        help='When ticked, totals and subtotals appear below the sections of the report.',
        readonly=False)

    account_return_periodicity = fields.Selection(
        selection=PERIODS,
        string="Delay units",
        help="Periodicity",
        required=True,
        default="monthly"
    )
    account_return_reminder_day = fields.Integer(string='Start from', default=7, required=True)
    account_tax_return_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        inverse='_inverse_account_tax_return_journal_id',
        domain=[('type', '=', 'general')],
        check_company=True,
    )
    account_revaluation_journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'general')], check_company=True)
    account_revaluation_expense_provision_account_id = fields.Many2one('account.account', string='Expense Provision Account', check_company=True)
    account_revaluation_income_provision_account_id = fields.Many2one('account.account', string='Income Provision Account', check_company=True)
    account_tax_unit_ids = fields.Many2many(string="Tax Units", comodel_name='account.tax.unit', help="The tax units this company belongs to.")
    account_representative_id = fields.Many2one('res.partner', string='Accounting Firm', index='btree_not_null',
                                                help="Specify an Accounting Firm that will act as a representative when exporting reports.")
    account_display_representative_field = fields.Boolean(compute='_compute_account_display_representative_field')
    account_last_return_cron_refresh = fields.Datetime()

    @api.depends('account_fiscal_country_id.code')
    def _compute_account_display_representative_field(self):
        country_set = self._get_countries_allowing_tax_representative()
        for record in self:
            record.account_display_representative_field = record.account_fiscal_country_id.code in country_set

    @api.depends('anglo_saxon_accounting')
    def _compute_totals_below_sections(self):
        for company in self:
            company.totals_below_sections = company.anglo_saxon_accounting

    def _inverse_account_tax_return_journal_id(self):
        self.account_tax_return_journal_id.show_on_dashboard = True

    def _get_countries_allowing_tax_representative(self):
        """ Returns a set containing the country codes of the countries for which
        it is possible to use a representative to submit the tax report.
        This function is a hook that needs to be overridden in localisation modules.
        """
        return set()

    def _get_tax_closing_journal(self):
        if not self.account_tax_return_journal_id:
            closing_journal = self.env['account.journal']
            for company in reversed(self.sudo().parent_ids):
                if journal := company.account_tax_return_journal_id:
                    closing_journal = journal
                    break
            if not closing_journal:
                closing_journal = self.env['account.journal'].sudo().search([
                    *self.env['account.journal']._check_company_domain(self),
                    ('code', 'in', ('TAX', 'TRTRN')),  # TRTRN for Backward compatibility
                    ('type', '=', 'general'),
                ], limit=1)
            if not closing_journal:
                closing_journal = self.env['account.journal'].sudo().create([{
                    'name': self.env._('Tax Returns'),
                    'code': 'TAX',
                    'type': 'general',
                    'company_id': self.id,
                    'currency_id': self.currency_id.id,
                    'show_on_dashboard': True,
                }])
            self.account_tax_return_journal_id = closing_journal
        return self.account_tax_return_journal_id

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._initiate_account_onboardings()

        # Set default values on every return types for this new company
        return_types = self.env['account.return.type'].sudo().search([
            '|',
            ('deadline_periodicity', '=', False),
            ('deadline_start_date', '=', False),
        ])
        return_types._set_default_values(companies)

        self.env['account.return.type']._generate_or_refresh_all_returns(companies.root_id)
        return companies

    def write(self, vals):
        root_companies_before = self.root_id
        res = super().write(vals)

        roots_to_recompute = root_companies_before | self.root_id
        if 'account_opening_date' in vals:
            self.env['account.return.type'].with_context(
                # 2 years to make sure we cover all cases, such as yearly returns with a deadline of more than 1 year.
                forced_date_from=self.account_opening_date - relativedelta(years=2),
                forced_date_to=datetime.date.today() + relativedelta(years=1),
            )._generate_or_refresh_all_returns(roots_to_recompute)

        elif set(vals) & {'account_return_periodicity', 'account_return_reminder_day', 'child_ids', 'parent_id'} and self.account_opening_date:
            self.env['account.return.type']._generate_or_refresh_all_returns(roots_to_recompute)

        return res

    def _get_available_tax_units(self, report, limit=None):
        """
        :return: A recordset of available tax units for this report and this company
        """
        self.ensure_one()
        return self.env['account.tax.unit'].search([
            ('company_ids', 'in', self.id),
            ('country_id', '=', report.country_id.id),
        ], limit=limit)

    def _get_branches_with_same_vat(self, accessible_only=False):
        """ Returns all companies among self and its branch hierachy (considering children and parents) that share the same VAT number
        as self. An empty VAT number is considered as being the same as the one of the closest parent with a VAT number.

        self is always returned as the first element of the resulting recordset (so that this can safely be used to restore the active company).

        Example::

            - main company ; vat = 123
                - branch 1
                    - branch 1_1
                - branch 2 ; vat = 456
                    - branch 2_1 ; vat = 789
                    - branch 2_2

        In this example, the following VAT numbers will be considered for each company::

            - main company: 123
            - branch 1: 123
            - branch 1_1: 123
            - branch 2: 456
            - branch 2_1: 789
            - branch 2_2: 456

        :param accessible_only: whether the returned companies should exclude companies that are not in self.env.companies
        """
        self.ensure_one()

        current = self.sudo()
        same_vat_branch_ids = [current.id] # Current is always available
        current_strict_parents = current.parent_ids - current
        if accessible_only:
            candidate_branches = current.root_id._accessible_branches()
        else:
            candidate_branches = self.env['res.company'].sudo().search([('id', 'child_of', current.root_id.ids)])

        current_vat_check_set = {current.vat} if current.vat else set()
        for branch in candidate_branches - current:
            parents_vat_set = set(filter(None, (branch.parent_ids - current_strict_parents).mapped('vat')))
            if parents_vat_set == current_vat_check_set:
                # If all the branches between the active company and branch (both included) share the same VAT number as the active company,
                # we want to add the branch to the selection.
                same_vat_branch_ids.append(branch.id)

        return self.browse(same_vat_branch_ids)
