from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import api, models, fields
from odoo.exceptions import UserError


class AccountReturnCreationWizard(models.TransientModel):
    _name = "account.return.creation.wizard"
    _description = "Return creation wizard"

    company_id = fields.Many2one(
        comodel_name='res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    category = fields.Selection(
        selection=[
            ('account_return', "Tax Return"),
            ('audit', "Audit"),
        ],
        default='account_return',
    )
    available_return_type_ids = fields.Many2many(
        string="Available Return Type",
        comodel_name='account.return.type',
        compute='_compute_available_return_type',
    )
    return_type_id = fields.Many2one(
        string="Return Type",
        comodel_name='account.return.type',
        required=True,
        compute="_compute_return_type_id",
        readonly=False,
        store=True,
        domain="[('id', 'in', available_return_type_ids)]",
    )
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)
    show_warning_wrong_dates = fields.Boolean(compute='_compute_warnings')
    show_warning_existing_return = fields.Boolean(compute='_compute_warnings')

    regulatory_compliance = fields.Boolean(string="Regulatory compliance", default=True)
    treasury_financing = fields.Boolean(string="Treasury and financing", default=True)
    purchases = fields.Boolean(string="Purchases", default=True)
    operating_expenses = fields.Boolean(string="Operating expenses", default=True)
    sales = fields.Boolean(string="Sales", default=True)
    inventory = fields.Boolean(string="Inventory", default=True)
    fixed_assets = fields.Boolean(string="Fixed assets", default=True)
    payroll = fields.Boolean(string="Payroll", default=True)
    government = fields.Boolean(string="Government", default=True)
    equity = fields.Boolean(string="Equity", default=True)
    other = fields.Boolean(string="Others", default=True)

    @api.depends('available_return_type_ids')
    def _compute_return_type_id(self):
        for wizard in self:
            if self.available_return_type_ids and not self.return_type_id:
                wizard.return_type_id = wizard.available_return_type_ids[0]
            else:
                wizard.return_type_id = False

    @api.onchange('return_type_id')
    def _onchange_return_type_id(self):
        today = fields.Date.context_today(self)
        if self.return_type_id:
            period_months = self.return_type_id._get_periodicity_months_delay(self.company_id)
            shifted_date = today - relativedelta(months=period_months)
            self.date_from, self.date_to = self.return_type_id._get_period_boundaries(self.company_id, shifted_date)
        else:
            self.date_from = self.date_to = False

    @api.depends('category')
    def _compute_available_return_type(self):
        return_type_by_country_and_category = self.env['account.return.type']._read_group(
            domain=[],
            groupby=['country_id', 'category'],
            aggregates=['id:recordset'],
        )
        country_return_type_map = defaultdict(
            lambda: defaultdict(lambda: self.env['account.return.type']))

        for country, category, returns in return_type_by_country_and_category:
            country_return_type_map[country][category] |= returns

        generic_tax_report = self.env.ref('account.generic_tax_report')

        for wizard in self:
            # For the company country, takes all the return types
            wizard_country_return_types = country_return_type_map[wizard.company_id.account_fiscal_country_id][wizard.category]

            # For the foreign fiscal positions, takes only the VAT return types
            foreign_vat_fpos_countries = self.env['account.fiscal.position'].search([
                *self.env['account.fiscal.position']._check_company_domain(wizard.company_id),
                ('foreign_vat', '!=', False),
            ]).mapped('country_id')

            foreign_return_types = self.env['account.return.type']
            for foreign_country in foreign_vat_fpos_countries:
                foreign_return_types |= country_return_type_map[foreign_country][wizard.category].filtered(lambda rt: rt.report_id.root_report_id == generic_tax_report)

            # Finally, includes the return types not linked to any country
            return_types_without_country = country_return_type_map[self.env['res.country']][wizard.category]

            # remove the generic tax report return type if company country tax return type available
            has_current_country_tax_return_type = wizard_country_return_types.filtered(lambda rt: rt.report_id.root_report_id == generic_tax_report)
            if has_current_country_tax_return_type:
                return_types_without_country = return_types_without_country.filtered(lambda rt: rt.report_id != generic_tax_report)

            wizard.available_return_type_ids = wizard_country_return_types + foreign_return_types + return_types_without_country

    @api.depends('date_from', 'date_to', 'return_type_id')
    def _compute_warnings(self):
        returns_companies_map = {
            (date_from, date_to, tuple(type_id.ids)): returns.mapped('company_ids')
            for date_from, date_to, type_id, returns in self.env['account.return']._read_group(
                domain=[],
                groupby=['date_from:day', 'date_to:day', 'type_id'],
                aggregates=['id:recordset'],
            )
        }

        for wizard in self:
            wizard.show_warning_wrong_dates = False
            wizard.show_warning_existing_return = False

            if not wizard.date_from or not wizard.date_to or not wizard.return_type_id:
                continue

            # ensures date_from and date_to are correctly set regarding return type boundaries
            date_pointer = wizard.date_from
            first_period = True

            while date_pointer < wizard.date_to:
                period_start, period_end = wizard.return_type_id._get_period_boundaries(wizard.company_id, date_pointer)

                if first_period and wizard.date_from != period_start:
                    wizard.show_warning_wrong_dates = True
                    break

                # check if a return already exists in this period
                companies_with_return_in_period = returns_companies_map.get((period_start, period_end, tuple(wizard.return_type_id.ids)), self.env['res.company'])
                if wizard.company_id in companies_with_return_in_period and wizard.category == 'account_return':
                    wizard.show_warning_existing_return = True

                date_pointer = period_end + relativedelta(days=1)
                first_period = False

            # Validate the last period ends exactly at date_to
            if date_pointer - relativedelta(days=1) != wizard.date_to:
                wizard.show_warning_wrong_dates = True

            # only display at most one warning
            if wizard.show_warning_wrong_dates:
                wizard.show_warning_existing_return = False

    def action_create_manual_account_returns(self):
        self.ensure_one()

        if self.show_warning_wrong_dates:
            raise UserError(self.env._("The selected range doesn't match any fiscal period."))

        if self.show_warning_existing_return:
            raise UserError(self.env._("A return already exists for the selected period."))

        all_branch_companies_with_same_vat = self.company_id._get_branches_with_same_vat()
        root_company = sorted(all_branch_companies_with_same_vat, key=lambda comp: len(comp.parent_path.split('/')))[0]
        tax_unit = self.env['account.tax.unit'].sudo().search([('company_ids', 'in', root_company.ids)], limit=1)
        apply_tax_unit = tax_unit and self.return_type_id.report_id.filter_multi_company == 'tax_units'
        company = tax_unit.main_company_id if apply_tax_unit else root_company
        if not company.has_access('read'):
            raise UserError(self.env._("You are trying to create returns for a company you don't have access to, please select it in the company selector"))

        returns_created = self.return_type_id.with_context(
            forced_date_from=fields.Date.to_string(self.date_from),
            forced_date_to=fields.Date.to_string(self.date_to),
            manually_created=True
        )._try_create_returns_for_fiscal_year(company, tax_unit, allow_duplicates=self.category == 'audit', bypass_period_check=True)
        returns_created.skipped_check_cycles = ','.join(
            v for k, v in {
                'regulatory_compliance': 'regulatory_compliance',
                'treasury_financing': 'treasury_financing',
                'purchases': 'purchases',
                'operating_expenses': 'operating_expenses',
                'sales': 'sales',
                'inventory': 'inventory',
                'fixed_assets': 'fixed_assets',
                'payroll': 'payroll',
                'government': 'state',
                'equity': 'equity',
                'other': 'other',
             }.items() if not self[k]
        )
        returns_created.refresh_checks()
        if len(returns_created) == 1:
            action = returns_created[0].action_open_account_return() if self.category == 'account_return' else returns_created[0].action_open_audit_return()

            return {
                'type': 'ir.actions.client',
                'tag': 'action_return_close_wizard',
                'params': {
                    'next_action': action
                }
            }

        return True
