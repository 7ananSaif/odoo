# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare

from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import uuid


class HrContractSalaryOffer(models.Model):
    _inherit = 'hr.contract.salary.offer'

    def _get_default_struct_id(self):
        return self.env['hr.version']._default_salary_structure().default_struct_id

    def _get_default_resource_calendar_id(self):
        return self.env.company.resource_calendar_id

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if self.env.context.get('default_is_simulation_offer'):
            result['access_token'] = uuid.uuid4().hex
        return result

    is_simulation_offer = fields.Boolean()
    monthly_wage = fields.Monetary(string="Monthly Wage", compute='_compute_monthly_wage', store=True, readonly=False)
    final_yearly_costs = fields.Monetary(compute='_compute_final_yearly_costs', store=True, readonly=False)
    budget_type = fields.Selection(
        selection=[('monthly_gross', 'Gross Per Month'), ('yearly_employer', 'Yearly Employer Cost')],
        default='yearly_employer',
        required=True
    )
    country_id = fields.Many2one(related='company_id.country_id')
    structure_id = fields.Many2one(
        'hr.payroll.structure',
        string="Salary Structure",
        default=_get_default_struct_id,
        domain="[('country_id', 'in', (country_id, False))]",
    )
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string="Working Schedule",
        default=_get_default_resource_calendar_id,
        check_company=True
    )
    simulation_employee_id = fields.Many2one('hr.employee', check_company=True,
        domain=[('contract_date_start', '!=', False)])
    gross_wage = fields.Monetary(compute='_compute_salary', store=True)
    net_wage = fields.Monetary(compute='_compute_salary', store=True)
    monthly_benefits = fields.Monetary(compute='_compute_salary', store=True)
    yearly_benefits = fields.Monetary(compute='_compute_salary', store=True)
    yearly_employer_cost = fields.Monetary(compute='_compute_salary', store=True)
    monthly_employer_cost = fields.Monetary(compute='_compute_salary', store=True)
    is_full_time = fields.Boolean(compute='_compute_salary', store=True)

    # DO NOT CALL THIS FUNCTION OUTSIDE OF A ROLLBACK SAVEPOINT
    def _get_version(self):
        self.ensure_one()
        version = super()._get_version().with_context(tracking_disable=True)
        version_vals = {}
        if self.is_simulation_offer:
            if self.simulation_employee_id:
                version = self.simulation_employee_id.version_id.with_context(version.env.context)
            version_vals.update({
                'structure_type_id': self.structure_id.type_id.id,
            })
        version_vals.update({
            'resource_calendar_id': version.resource_calendar_id.id or self.resource_calendar_id.id or self._get_default_resource_calendar_id().id,
            version._get_contract_wage_field(): self.monthly_wage,
            'wage_with_holidays': self.monthly_wage,
        })
        if not version.contract_date_start:
            if self.employee_id and self.employee_id.current_version_id and self.employee_id.current_version_id.contract_date_start:
                self.employee_id.current_version_id.with_context(tracking_disable=True).write({
                    'contract_date_end': version.date_version - relativedelta(days=1)
                })
            version_vals.update({
                'contract_date_start': version.date_version
            })
        version.write(version_vals)
        version._inverse_wage_with_holidays()
        return version

    @api.onchange('simulation_employee_id')
    def _onchange_simulation_employee_id(self):
        if self.simulation_employee_id:
            version = self.simulation_employee_id.current_version_id
            self.monthly_wage = version._get_contract_wage()
            self.resource_calendar_id = version.resource_calendar_id
            self.structure_id = version.structure_type_id.default_struct_id

    @api.depends('final_yearly_costs')
    def _compute_monthly_wage(self):
        monthly_wage_by_offer = {}
        self.env.flush_all()
        with self.env.cr.savepoint(flush=False) as sp:
            for offer in self.with_context(salary_simulation=True):
                version = offer._get_version()
                monthly_wage_by_offer[offer] = version._get_gross_from_employer_costs(offer.final_yearly_costs)

            self.env.cr.precommit.data.pop('mail.tracking.hr.version', {})
            self.env.flush_all()
            sp.rollback()

        # Invalidating the model is needed to be sure that the contract_template_id has the correct data. Even with
        # the rollback, the recordset in cache could still hold some wrong values that were rollbacked
        self.env['hr.version'].invalidate_model()

        for offer in self:
            offer.monthly_wage = monthly_wage_by_offer[offer]

    @api.depends('monthly_wage')
    def _compute_final_yearly_costs(self):
        final_yearly_costs_by_offer = {}
        self.env.flush_all()
        with self.env.cr.savepoint(flush=False) as sp:
            for offer in self.with_context(salary_simulation=True):
                version = offer._get_version()
                final_yearly_costs_by_offer[offer] = version._get_employer_costs_from_gross(offer.monthly_wage)

            self.env.cr.precommit.data.pop('mail.tracking.hr.version', {})
            self.env.flush_all()
            sp.rollback()

        # Invalidating the model is needed to be sure that the contract_template_id has the correct data. Even with
        # the rollback, the recordset in cache could still hold some wrong values that were rollbacked
        self.env['hr.version'].invalidate_model()

        for offer in self:
            offer.final_yearly_costs = final_yearly_costs_by_offer[offer]

    @api.depends('monthly_wage', 'structure_id', 'resource_calendar_id')
    def _compute_salary(self) -> None:
        vals_by_offer = {}
        self.env.flush_all()
        with self.env.cr.savepoint(flush=False) as sp:
            for offer in self.with_context(salary_simulation=True):
                version = offer._get_version()
                payslip = version._generate_salary_simulation_payslip()
                yearly_employer_cost = version._get_employer_costs_from_gross(version._get_contract_wage())
                monthly_benefits, yearly_benefits = self._get_benefits(version)
                vals_by_offer[offer] = {
                    'is_full_time': float_compare(version.work_time_rate, 1.0, 4) == 0,
                    'gross_wage': payslip._get_line_values(['BASIC'])['BASIC'][payslip.id]['total'],
                    'net_wage': payslip._get_line_values(['NET'])['NET'][payslip.id]['total'],
                    'monthly_benefits': monthly_benefits,
                    'yearly_benefits': yearly_benefits,
                    'yearly_employer_cost': yearly_employer_cost,
                    'monthly_employer_cost': round(yearly_employer_cost / 12, 2),
                }
            self.env.cr.precommit.data.pop('mail.tracking.hr.version', {})
            self.env.flush_all()
            sp.rollback()

        # Invalidating the model is needed to be sure that the contract_template_id has the correct data. Even with
        # the rollback, the recordset in cache could still hold some wrong values that were rollbacked
        self.env['hr.version'].invalidate_model()

        for offer in self:
            offer.update(vals_by_offer[offer])

    def _get_benefits(self, version):
        monthly_benefit_category = self.env.ref('hr_contract_salary.hr_contract_salary_resume_category_monthly_benefits')
        yearly_benefit_category = self.env.ref('hr_contract_salary.hr_contract_salary_resume_category_yearly_benefits')
        resume_lines = self.env['hr.contract.salary.resume'].sudo().with_company(version.company_id).search([
            '|',
            ('structure_type_id', '=', False),
            ('structure_type_id', '=', version.structure_type_id.id),
            ('value_type', '=', 'sum'),
            ('category_id', 'in', (monthly_benefit_category.id, yearly_benefit_category.id))
        ])
        result = defaultdict(int)
        for resume_line in resume_lines:
            value = 0
            for benefit in resume_line.benefit_ids:
                if not benefit.fold_field or (benefit.fold_field and version[benefit.fold_field]):
                    field = benefit.field
                    value += version[field] if benefit.source == 'field' else version._get_property_input_value(benefit.salary_rule_id.code)
            result[resume_line.category_id.id] += round(float(value), 2)
        return result[monthly_benefit_category.id], result[yearly_benefit_category.id]

    @api.model
    def action_cron_remove_simulation_offers(self):
        simulation_offers = self.env['hr.contract.salary.offer'].search([('is_simulation_offer', '=', True)])
        older_than_one_month_offers = simulation_offers.filtered(
            lambda offer: offer.offer_create_date < (date.today() - relativedelta(month=1))
        )
        return older_than_one_month_offers.unlink()

    def action_open_salary_configurator(self):
        self.ensure_one()
        self.resource_calendar_id = self.resource_calendar_id or self._get_default_resource_calendar_id()
        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }
