# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.models import MAGIC_COLUMNS
from odoo.exceptions import ValidationError
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)


class HrVersion(models.Model):
    _inherit = 'hr.version'

    def _default_get_template_warning(self):
        sign_template_count = self.env['sign.template'].sudo().search_count([('active', '=', True)], limit=1)
        return not sign_template_count and _('No templates are configured yet. Do you want to set up first one?')

    origin_version_id = fields.Many2one(
        'hr.version', string="Origin Contract", domain="[('company_id', '=', company_id)]",
        groups="hr.group_hr_user", help="The contract from which this contract has been duplicated.", tracking=True)
    is_origin_contract_template = fields.Boolean(
        compute='_compute_is_origin_contract_template', string='Is origin contract a contract template?',
        groups="hr.group_hr_user", readonly=True)
    hash_token = fields.Char('Created From Token', groups="hr.group_hr_user", tracking=True)
    applicant_id = fields.Many2one('hr.applicant', groups="hr.group_hr_user",
                                   domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=True)
    contract_reviews_count = fields.Integer(compute="_compute_contract_reviews_count",
                                            string="Proposed Contracts Count")
    contract_template_id = fields.Many2one(default=lambda self: self.job_id.contract_template_id or False)
    sign_template_id = fields.Many2one(
        'sign.template', compute='_compute_sign_template_id', readonly=False, store=True, copy=True,
        string="New Contract Template", groups="hr.group_hr_user",
        help="Default document that the applicant will have to sign to accept a contract offer.")
    sign_template_signatories_ids = fields.One2many('hr.contract.signatory', 'contract_template_id',
                                                    compute="_compute_sign_template_signatories_ids", store=True,
                                                    readonly=False, groups="hr.group_hr_user")
    contract_update_template_id = fields.Many2one(
        'sign.template', string="Contract Update", groups="hr.group_hr_user",
        compute='_compute_contract_update_template_id', store=True, readonly=False, copy=True,
        help="Default document that the employee will have to sign to update his contract.")
    contract_update_signatories_ids = fields.One2many('hr.contract.signatory', 'update_contract_template_id',
                                                      compute="_compute_contract_update_signatories_ids", store=True,
                                                      readonly=False, groups="hr.group_hr_user")
    signatures_count = fields.Integer(compute='_compute_signatures_count', string='# Signatures',
        help="The number of signatures on the pdf contract with the most signatures.", groups="hr.group_hr_user")
    image_1920_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    image_1920 = fields.Image(related='employee_id.image_1920', groups="hr.group_hr_manager", readonly=False)
    # YTI FIXME: holidays and wage_with_holidays are defined twice...
    holidays = fields.Float(string='Extra Time Off', groups="hr.group_hr_user",
        help="Number of days of paid leaves the employee gets per year.", tracking=True)
    wage_with_holidays = fields.Monetary(compute='_compute_wage_with_holidays', inverse='_inverse_wage_with_holidays',
        tracking=True, string="Wage with Holidays", groups="hr.group_hr_manager")
    wage_on_signature = fields.Monetary(string="Wage on Signature", tracking=True, aggregator="avg",
                                        groups="hr.group_hr_manager")
    salary_offer_ids = fields.One2many('hr.contract.salary.offer', 'employee_version_id', groups="hr.group_hr_manager", tracking=True)
    originated_offer_id = fields.Many2one('hr.contract.salary.offer', help="The original offer",
                                          groups="hr.group_hr_user", tracking=True)
    salary_offers_count = fields.Integer(compute='_compute_salary_offers_count', compute_sudo=True)
    template_warning = fields.Char(default=_default_get_template_warning, store=False, groups="hr.group_hr_user")

    # Employer costs fields
    final_yearly_costs = fields.Monetary(
        compute='_compute_final_yearly_costs',
        readonly=False, store=True,
        string="Yearly Cost",
        tracking=True,
        aggregator="avg",
        groups="hr.group_hr_manager")
    monthly_yearly_costs = fields.Monetary(
        compute='_compute_monthly_yearly_costs', string='Monthly Cost', readonly=True, groups="hr.group_hr_manager")

    @api.constrains('sign_template_signatories_ids')
    def _check_signatories_unicity(self):
        for version in self:
            roles = [i.sign_role_id for i in version.sign_template_signatories_ids]
            if len(roles) != len(set(roles)):
                raise ValidationError(_("You cannot have multiple person responsible for the same role on contract signature template."))

    @api.constrains('contract_update_signatories_ids')
    def _check_update_signatories_unicity(self):
        for version in self:
            roles = [i.sign_role_id for i in version.contract_update_signatories_ids]
            if len(roles) != len(set(roles)):
                raise ValidationError(_("You cannot have multiple person responsible for the same role on contract update signature template."))

    @api.depends('sign_template_id')
    def _compute_sign_template_signatories_ids(self):
        for version in self:
            version.sign_template_signatories_ids = self.env['hr.contract.signatory'].create_empty_signatories(version.sign_template_id)

    @api.depends('contract_update_template_id')
    def _compute_contract_update_signatories_ids(self):
        for version in self:
            version.contract_update_signatories_ids = self.env['hr.contract.signatory'].create_empty_signatories(version.contract_update_template_id)

    @api.constrains('hr_responsible_id', 'sign_template_id')
    def _check_hr_responsible_id(self):
        for version in self:
            if version.sign_template_id:
                if not version.hr_responsible_id.has_group('sign.group_sign_user'):
                    raise ValidationError(_("HR Responsible %s should be a user of Sign when New Contract Document Template is specified", version.hr_responsible_id.name))
                if not version.hr_responsible_id.email_formatted:
                    raise ValidationError(_("HR Responsible %s should have a valid email address when New Contract Document Template is specified", version.hr_responsible_id.name))

    @api.depends('wage', 'wage_on_signature')
    def _compute_contract_wage(self):
        super()._compute_contract_wage()

    def _get_contract_wage_field(self):
        self.ensure_one()
        if self._is_struct_from_country('BE'):
            return 'wage_on_signature'
        return super()._get_contract_wage_field()

    @api.depends('origin_version_id')
    def _compute_is_origin_contract_template(self):
        for version in self:
            version.is_origin_contract_template = version.origin_version_id and not version.origin_version_id.employee_id

    def _compute_salary_offers_count(self):
        offers_data = self.env['hr.contract.salary.offer']._read_group(
            domain=[('employee_version_id', 'in', self.ids)],
            groupby=['employee_version_id'],
            aggregates=['__count'])
        mapped_data = {version.id: count for version, count in offers_data}
        for version in self:
            version.salary_offers_count = mapped_data.get(version.id, 0)

    def _get_yearly_cost_sacrifice_ratio(self):
        return 1.0 - self.holidays / 231.0

    def _get_yearly_cost_sacrifice_fixed(self):
        return 0.0

    def _get_yearly_cost_from_wage_with_holidays(self, wage_with_holidays=False):
        self.ensure_one()
        ratio = self._get_yearly_cost_sacrifice_ratio()
        fixed = self._get_yearly_cost_sacrifice_fixed()
        if wage_with_holidays:
            return (self._get_benefits_costs() + self._get_salary_costs_factor() * wage_with_holidays + fixed) / ratio
        return self.final_yearly_costs * ratio - fixed

    def _get_yearly_cost_from_wage(self):
        self.ensure_one()
        fixed = self._get_yearly_cost_sacrifice_fixed()
        return self._get_benefits_costs() + self._get_salary_costs_factor() * self.wage + fixed

    def _is_salary_sacrifice(self):
        self.ensure_one()
        return self.holidays

    @api.depends('holidays', 'wage', 'final_yearly_costs')
    def _compute_wage_with_holidays(self):
        for version in self:
            if version._is_salary_sacrifice():
                yearly_cost = version._get_yearly_cost_from_wage_with_holidays()
                version.wage_with_holidays = version._get_gross_from_employer_costs(yearly_cost)
            else:
                version.wage_with_holidays = version.wage

    def _inverse_wage_with_holidays(self):
        for version in self:
            if version._is_salary_sacrifice():
                yearly = version._get_yearly_cost_from_wage_with_holidays(version.wage_with_holidays)
                version.wage = version._get_gross_from_employer_costs(yearly)
            else:
                if version.wage != version.wage_with_holidays:
                    version.wage = version.wage_with_holidays

    def _get_benefit_description(self, benefit, new_value=None):
        self.ensure_one()
        if hasattr(self, '_get_description_%s' % benefit.field):
            description = getattr(self, '_get_description_%s' % benefit.field)(new_value)
        else:
            description = benefit.description
        return html_sanitize(description)

    def _get_benefit_fields(self, triggers=True):
        types = ('float', 'integer', 'monetary', 'boolean', 'properties')
        if not triggers:
            types += ('text',)
        nonstored_whitelist = self._benefit_white_list()
        benefit_fields = {
            field.name
            for field in self._fields.values()
            if field.type in types and (field.store or not field.store and field.name in nonstored_whitelist) and not field.name.startswith("x_studio_")
        }
        if not triggers:
            benefit_fields |= {'wage_with_holidays'}
        return tuple(benefit_fields - self._benefit_black_list())

    def _get_employee_vals_to_update(self):
        vals = super()._get_employee_vals_to_update()
        if self.originated_offer_id and self.originated_offer_id.job_title:
            vals['job_title'] = self.originated_offer_id.job_title
        return vals

    @api.model
    def _benefit_black_list(self):
        return set(MAGIC_COLUMNS + [
            'wage_on_signature', 'active',
            'date_generated_from', 'date_generated_to'])

    @api.model
    def _benefit_white_list(self):
        return []

    @api.depends(lambda self: (
        'wage',
        'structure_type_id.salary_benefits_ids.res_field_id',
        'structure_type_id.salary_benefits_ids.cost_res_field_id',
        *self._get_benefit_fields()))
    def _compute_final_yearly_costs(self):
        for version in self:
            if abs(version.final_yearly_costs - version._get_yearly_cost_from_wage()) > 0.10:
                version.final_yearly_costs = version._get_yearly_cost_from_wage()

    @api.depends('company_id', 'job_id')
    def _compute_structure_type_id(self):
        versions = self.env['hr.version']
        for version in self:
            if version.job_id and version.job_id.contract_template_id and version.job_id.contract_template_id.structure_type_id:
                version.structure_type_id = version.job_id.contract_template_id.structure_type_id
            else:
                versions |= version
        super(HrVersion, versions)._compute_structure_type_id()

    @api.onchange("wage_with_holidays")
    def _onchange_wage_with_holidays(self):
        self._inverse_wage_with_holidays()

    @api.onchange('final_yearly_costs')
    def _onchange_final_yearly_costs(self):
        final_yearly_costs = self.final_yearly_costs
        self.wage = self._get_gross_from_employer_costs(final_yearly_costs)
        self.env.remove_to_compute(self._fields['final_yearly_costs'], self)
        self.final_yearly_costs = final_yearly_costs

    @api.depends('final_yearly_costs')
    def _compute_monthly_yearly_costs(self):
        for version in self:
            version.monthly_yearly_costs = version.final_yearly_costs / 12.0

    def _get_benefits_costs(self):
        self.ensure_one()
        benefits = self.env['hr.contract.salary.benefit'].search([
            ('structure_type_id', '=', self.structure_type_id.id),
            ('cost_res_field_id', '!=', False),
        ])
        if not benefits:
            return 0
        monthly_benefits = benefits.filtered(lambda a: a.benefit_type_id.periodicity == 'monthly')
        monthly_cost = sum(self[benefit.cost_field] or 0 for benefit in monthly_benefits if benefit.cost_field in self)
        yearly_cost = sum(self[benefit.cost_field] or 0 for benefit in benefits - monthly_benefits if benefit.cost_field in self)
        return monthly_cost * 12 + yearly_cost

    def _get_gross_from_employer_costs(self, yearly_cost):
        self.ensure_one()
        remaining_for_gross = yearly_cost - self._get_benefits_costs()
        salary_costs_factor = self._get_salary_costs_factor()
        if salary_costs_factor:
            return remaining_for_gross / salary_costs_factor
        return 0

    def _get_employer_costs_from_gross(self, gross):
        self.ensure_one()
        return (gross * self._get_salary_costs_factor()) + self._get_benefits_costs()

    @api.depends('sign_request_ids.nb_closed')
    def _compute_signatures_count(self):
        for version in self:
            version.signatures_count = max(version.sign_request_ids.mapped('nb_closed') or [0])

    @api.depends('origin_version_id')
    def _compute_contract_reviews_count(self):
        data = dict(self.with_context(active_test=False)._read_group(
            [('origin_version_id', 'in', self.ids)],
            ['origin_version_id'],
            ['__count'],
        ))
        for version in self:
            version.contract_reviews_count = data.get(version, 0)

    @api.depends('contract_template_id')
    def _compute_sign_template_id(self):
        for version in self:
            if version.contract_template_id:
                version.sign_template_id = version.contract_template_id.sign_template_id

    @api.depends('contract_template_id')
    def _compute_contract_update_template_id(self):
        for version in self:
            if version.contract_template_id and version.id != version.contract_template_id.id:
                version.contract_update_template_id = version.contract_template_id.contract_update_template_id

    def action_show_contract_reviews(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.version",
            "views": [[False, "list"], [False, "form"]],
            "domain": [["origin_version_id", "=", self.id]],
            "context": {"active_test": False},
            "name": "Contracts Reviews",
        }

    def action_generate_offer(self):

        offer_validity_period = int(self.env['ir.config_parameter'].sudo().get_param(
            'hr_contract_salary.employee_salary_simulator_link_validity', default=30))
        offer_values = self._get_offer_values()
        offer_values['validity_days_count'] = offer_validity_period
        offer = self.env['hr.contract.salary.offer'].with_context(
            default_contract_template_id=self.id).create(offer_values)

        self.message_post(
            body=_("An %(offer)s has been sent by %(user)s to the employee (mail: %(email)s)",
                    offer=Markup("<a href='#' data-oe-model='hr.contract.salary.offer' data-oe-id='{offer_id}'>Offer</a>")
                    .format(offer_id=offer.id),
                    user=self.env.user.name,
                    email=self.employee_id.work_email
            )
        )

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.contract.salary.offer',
            'res_id': offer.id,
            'views': [(False, 'form')],
            'context': {'active_model': 'hr.version', 'default_employee_version_id': self.id}
        }

    def _get_offer_values(self):
        self.ensure_one()
        return {
            'company_id': self.company_id.id,
            'contract_template_id': self.id,
            'employee_version_id': self.id,
            'final_yearly_costs': self.final_yearly_costs,
            'job_title': self.job_id.name,
            'employee_job_id':  self.job_id.id,
            'department_id': self.department_id.id,
        }

    def _get_values_dict(self):
        self.ensure_one()
        return self.read(load=None)[0]

    def _get_wage_to_apply(self):
        # To be overriden in localizations if a new wage applies depending on selected benefits
        self.ensure_one()
        return self.wage_with_holidays

    def send_offer(self):
        self.ensure_one()
        try:
            template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
        except ValueError:
            template_id = False
        path = '/salary_package/contract/' + str(self.id)
        ctx = {
            'default_email_layout_xmlid': 'mail.mail_notification_light',
            'default_model': 'hr.version',
            'default_res_ids': self.ids,
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'salary_package_url': self.env['hr.version'].get_base_url() + path,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }

    def action_archive(self):
        res = super().action_archive()
        job_positions = self.env['hr.job'].search([('contract_template_id', 'in', self.ids)])
        job_positions.contract_template_id = False
        return res
