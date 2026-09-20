import ast

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.fields import Domain
from odoo.tools.float_utils import float_compare


class HrVersion(models.Model):
    _inherit = 'hr.version'

    image_1920_filename = fields.Char(tracking=True)
    id_card_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    id_card = fields.Binary(related='employee_id.id_card', groups="hr.group_hr_manager", readonly=False)
    driving_license_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    driving_license = fields.Binary(related='employee_id.driving_license', groups="hr.group_hr_manager", readonly=False)
    mobile_invoice_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    mobile_invoice = fields.Binary(related='employee_id.mobile_invoice', groups="hr.group_hr_manager", readonly=False)
    sim_card_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    sim_card = fields.Binary(related='employee_id.sim_card', groups="hr.group_hr_manager", readonly=False)
    internet_invoice_filename = fields.Char(groups="hr.group_hr_user", tracking=True)
    internet_invoice = fields.Binary(related="employee_id.internet_invoice", groups="hr.group_hr_manager", readonly=False)
    double_holiday_wage = fields.Monetary(compute='_compute_double_holiday_wage', groups="hr_payroll.group_hr_payroll_user")
    contract_type_id = fields.Many2one('hr.contract.type', "Contract Type",
                                       default=lambda self: self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_cdi',
                                                                         raise_if_not_found=False) if self.env.company.country_id.code == "BE" else self.env['hr.contract.type'])
    l10n_be_bicyle_cost = fields.Float(compute='_compute_l10n_be_bicyle_cost', groups="hr_payroll.group_hr_payroll_user")

    l10n_be_mobility_budget_amount = fields.Monetary(
        string="Mobility Budget Amount",
        store=True,
        compute="_compute_l10n_be_mobility_budget_amount"
    )

    l10n_be_wage_with_mobility_budget = fields.Monetary(
        tracking=True, string="Wage with Mobility Budget",
        compute="_compute_l10n_be_wage_with_mobility_budget",
        store=True
    )

    @api.depends('has_bicycle')
    def _compute_l10n_be_bicyle_cost(self):
        for version in self:
            if not version.has_bicycle:
                version.l10n_be_bicyle_cost = 0
            else:
                version.l10n_be_bicyle_cost = self._get_private_bicycle_cost(version.employee_id.km_home_work)

    @api.depends('l10n_be_mobility_budget', 'wage_with_holidays')
    def _compute_l10n_be_mobility_budget_amount(self):
        mobility_budget_max = self.env['hr.rule.parameter']._get_parameter_from_code("mobility_budget_max", fields.Date.today(), raise_if_not_found=False) or 16875
        mobility_budget_min = self.env['hr.rule.parameter']._get_parameter_from_code("mobility_budget_min", fields.Date.today(), raise_if_not_found=False) or 3164

        minimum_wage = self.env['hr.rule.parameter']._get_parameter_from_code('cp200_min_gross_wage', fields.Date.today(), raise_if_not_found=False)
        for version in self:
            if version.l10n_be_mobility_budget:
                base = self.env.context.get(
                    'salary_simulation_full_time_wage_on_holidays',
                    version.wage_with_holidays
                )
                raw_mb = min(mobility_budget_max, base * 13.0 / 5.0)

                # find the right budget to not get under the minimum wage
                current_yearly_cost = self.env.context.get(
                    'salary_simulation_full_time_yearly_cost',
                    version._get_yearly_cost_from_wage_with_holidays() if version._is_salary_sacrifice() else version.final_yearly_costs
                )
                version_mobility_budget_min = mobility_budget_min
                version_mobility_budget_max = raw_mb
                while float_compare(version_mobility_budget_min, version_mobility_budget_max, precision_digits=2) == -1:
                    version_mobility_budget = (version_mobility_budget_max + version_mobility_budget_min) / 2
                    wage_with_mobility_budget = version._get_gross_from_employer_costs(current_yearly_cost - version_mobility_budget)
                    if wage_with_mobility_budget < minimum_wage and minimum_wage:
                        version_mobility_budget_max = version_mobility_budget
                    else:
                        version_mobility_budget_min = version_mobility_budget

                raw_mb = version_mobility_budget_min
                version.l10n_be_mobility_budget_amount = raw_mb
            else:
                version.l10n_be_mobility_budget_amount = 0.0

    @api.depends('l10n_be_mobility_budget', 'l10n_be_mobility_budget_amount', 'wage_with_holidays')
    def _compute_l10n_be_wage_with_mobility_budget(self):
        for version in self:
            if version._is_salary_sacrifice():
                yearly_cost = version._get_yearly_cost_from_wage_with_holidays()
                version.l10n_be_wage_with_mobility_budget = version._get_gross_from_employer_costs(yearly_cost - version.l10n_be_mobility_budget_amount)
            else:
                version.l10n_be_wage_with_mobility_budget = version._get_gross_from_employer_costs(version.final_yearly_costs - version.l10n_be_mobility_budget_amount)

    @api.model
    def _get_wage_to_apply(self):
        self.ensure_one()
        if self.l10n_be_mobility_budget:
            return self.l10n_be_wage_with_mobility_budget
        return super()._get_wage_to_apply()

    @api.model
    def _get_private_bicycle_cost(self, distance):
        amount_per_km = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('cp200_cycle_reimbursement_per_km', raise_if_not_found=False) or 0.20
        amount_max = self.env['hr.rule.parameter'].sudo()._get_parameter_from_code('cp200_cycle_reimbursement_max', raise_if_not_found=False) or 8
        return 4 * min(amount_max, amount_per_km * distance * 2)

    @api.depends(
        'wage_with_holidays', 'wage_on_signature',
        'employee_id.l10n_be_scale_seniority', 'job_id.l10n_be_scale_category',
        'work_time_rate', 'l10n_be_time_credit', 'resource_calendar_id.work_time_rate')
    def _compute_l10n_be_is_below_scale(self):
        super()._compute_l10n_be_is_below_scale()

    @api.depends('wage_with_holidays')
    def _compute_double_holiday_wage(self):
        for version in self:
            version.double_holiday_wage = version._get_wage_to_apply() * 0.92

    @api.model
    def _benefit_white_list(self):
        return super()._benefit_white_list() + [
            'private_car_reimbursed_amount',
            'yearly_commission_cost',
            'meal_voucher_average_monthly_amount',
            'l10n_be_bicyle_cost',
            'double_holiday_wage',
        ]

    def _get_benefit_values_company_car_total_depreciated_cost(self, version_vals, benefits):
        has_car = benefits['fold_company_car_total_depreciated_cost']
        selected_car = benefits.get('select_company_car_total_depreciated_cost')
        if not has_car or not selected_car:
            return {
                'transport_mode_car': False,
                'new_car': False,
                'new_car_model_id': False,
                'car_id': False,
            }
        car, car_id = selected_car.split('-')
        new_car = car == 'new'
        if new_car:
            return {
                'transport_mode_car': True,
                'new_car': True,
                'new_car_model_id': int(car_id),
                'car_id': False,
            }
        return {
            'transport_mode_car': True,
            'new_car': False,
            'new_car_model_id': False,
            'car_id': int(car_id),
        }

    def _get_benefit_values_company_bike_depreciated_cost(self, version_vals, benefits):
        has_bike = benefits['fold_company_bike_depreciated_cost']
        selected_bike = benefits.get('select_company_bike_depreciated_cost', None)
        if not has_bike or not selected_bike:
            return {
                'transport_mode_bike': False,
                'new_bike_model_id': False,
                'bike_id': False,
            }
        bike, bike_id = selected_bike.split('-')
        new_bike = bike == 'new'
        if new_bike:
            return {
                'transport_mode_bike': False,
                'new_bike': True,
                'new_bike_model_id': int(bike_id),
                'bike_id': False,
            }
        return {
            'transport_mode_bike': True,
            'new_bike': False,
            'new_bike_model_id': False,
            'bike_id': int(bike_id),
        }

    def _get_benefit_values_wishlist_car_total_depreciated_cost(self, version_vals, benefits):
        if benefits.get('fold_wishlist_car_total_depreciated_cost', False):
            model_id = benefits['select_wishlist_car_total_depreciated_cost'].split('-')[1]
            return {
                'new_car': True,
                'new_car_model_id': int(model_id)
            }
        else:
            return {}

    def _get_benefit_values_insured_relative_spouse(self, version_vals, benefits):
        return {'insured_relative_spouse': benefits['fold_insured_relative_spouse']}

    def _get_benefit_values_l10n_be_ambulatory_insured_spouse(self, version_vals, benefits):
        return {'l10n_be_ambulatory_insured_spouse': benefits['fold_l10n_be_ambulatory_insured_spouse']}

    def _get_description_company_car_total_depreciated_cost(self, new_value=None):
        benefit = self.env.ref('l10n_be_hr_contract_salary.l10n_be_transport_company_car')
        description = benefit.description or ""
        if not new_value:
            if self.car_id:
                new_value = 'old-%s' % self.car_id.id
            elif self.new_car_model_id:
                new_value = 'new-%s' % self.new_car_model_id.id
            else:
                return description
        car_option, vehicle_id = new_value.split('-')
        try:
            vehicle_id = int(vehicle_id)
        except ValueError:
            return description
        if car_option == "new":
            vehicle = self.env['fleet.vehicle.model'].with_company(self.company_id).sudo().browse(vehicle_id)
        else:
            vehicle = self.env['fleet.vehicle'].with_company(self.company_id).sudo().browse(vehicle_id)

        is_new = bool(car_option == "new")

        car_elements = self._get_company_car_description_values(vehicle, is_new)
        description += Markup('<ul>%s</ul>') % Markup().join([Markup('<li>%s: %s</li>') % (key, value) for key, value in car_elements.items() if value])
        return description

    def _get_description_wishlist_car_total_depreciated_cost(self, new_value=None):
        benefit = self.env.ref('l10n_be_hr_contract_salary.l10n_be_transport_new_car')
        description = benefit.description or ""
        if not new_value:
            return description
        else:
            vehicle_id = new_value.split('-')[1]
            vehicle = self.env['fleet.vehicle.model'].with_company(self.company_id).sudo().browse(int(vehicle_id))
            car_elements = self._get_company_car_description_values(vehicle, True)
            description += Markup('<ul>%s</ul>') % Markup().join([Markup('<li>%s: %s</li>') % (key, value) for key, value in car_elements.items() if value])

        return description

    def _get_description_company_bike_depreciated_cost(self, new_value):
        benefit = self.env.ref('l10n_be_hr_contract_salary.l10n_be_transport_company_bike')
        description = benefit.description or ""
        if not new_value:
            if self.bike_id:
                new_value = 'old-%s' % self.bike_id.id
            else:
                return description
        bike_option, bike_id = new_value.split('-')
        if bike_option == "new":
            bike = self.env['fleet.vehicle.model'].with_company(self.company_id).sudo().browse(int(bike_id))
        else:
            bike = self.env['fleet.vehicle'].with_company(self.company_id).sudo().browse(int(bike_id))

        bike_elements = {
            'Monthly Cost': _("%s € (Rent)", bike.total_depreciated_cost if bike_option == "old" else bike.default_total_depreciated_cost),
            'Electric Assistance': _("Yes") if bike.electric_assistance else _("No"),
            'Color': bike.color,
            'Bike Frame Type': bike.frame_type if bike_option == "old" else False,
            'Frame Size (cm)': bike.frame_size if bike_option == "old" else False,
        }

        description += Markup('<ul>%s</ul>') % Markup().join(Markup('<li>%s: %s</li>') % (key, value) for key, value in bike_elements.items() if value)

        return description

    def _get_company_car_description_values(self, vehicle_id, is_new):
        vehicle_range = _("%(range)s %(unit)s",
            range=vehicle_id.vehicle_range, unit=vehicle_id.range_unit) if vehicle_id.vehicle_range else False
        if is_new:
            co2 = _("%(co2)s %(unit)s", co2=vehicle_id.default_co2,
                unit=vehicle_id.co2_emission_unit) if vehicle_id.default_co2 else False
            fuel_type = vehicle_id.default_fuel_type
            transmission = vehicle_id.transmission
            door_number = odometer = immatriculation = trailer_hook = False
            bik_display = "%s €" % round(vehicle_id.default_atn, 2)
            monthly_cost_display = _("%(co2_fee)s € (CO2 Fee) + %(rent)s € (Rent)", co2_fee=round(vehicle_id.co2_fee, 2), rent=round(vehicle_id.default_total_depreciated_cost - vehicle_id.co2_fee, 2))
        else:
            co2 = _("%(co2)s %(unit)s", co2=vehicle_id.co2,
                unit=vehicle_id.co2_emission_unit) if vehicle_id.co2 else False
            fuel_type = vehicle_id.fuel_type
            door_number = vehicle_id.doors
            odometer = vehicle_id.odometer
            immatriculation = vehicle_id.acquisition_date
            transmission = vehicle_id.transmission
            trailer_hook = "Yes" if vehicle_id.trailer_hook else "No"
            bik_display = "%s €" % round(vehicle_id.atn, 2)
            monthly_cost_display = _("%(co2_fee)s € (CO2 Fee) + %(rent)s € (Rent)", co2_fee=round(vehicle_id.co2_fee, 2), rent=round(vehicle_id.total_depreciated_cost - vehicle_id.co2_fee, 2))

        car_elements = {
            'CO2 Emission': co2,
            'Monthly Cost': monthly_cost_display,
            'Fuel Type': fuel_type,
            'Range': vehicle_range,
            'BIK': bik_display,
            'Transmission': transmission,
            'Doors Number': door_number,
            'Trailer Hook': trailer_hook,
            'Odometer': odometer,
            'Immatriculation Date': immatriculation
        }
        return car_elements

    def _get_description_commission_on_target(self, new_value=None):
        self.ensure_one()
        return '<span class="form-text">The commission is scalable and starts from the 1st € sold. The commission plan has stages with accelerators. At 100%%, 3 months are paid in Warrant which results to a monthly NET commission value of %s € and 9 months in cash which result in a GROSS monthly commission of %s €, taxable like your usual monthly pay.</span>' % (round(self.warrant_value_employee, 2), round(self.commission_on_target, 2))

    def _get_benefit_values_ip_value(self, version_vals, benefits):
        return {
            'ip': benefits['ip_value'] and ast.literal_eval(benefits['ip_value']),
            'ip_wage_rate': version_vals.get('ip_wage_rate')
        }

    def _get_available_cars_domain(self):
        return Domain.AND(
            [
                super()._get_available_cars_domain(),
                Domain('state_id.hide_in_offer', '=', False),
            ],
        )
