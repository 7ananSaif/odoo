# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict

from odoo import fields, _
from odoo.addons.hr_contract_salary.controllers import main
from odoo.addons.sign.controllers.main import Sign
from odoo.http import route, request

ODOMETER_UNITS = {'kilometers': 'km', 'miles': 'mi'}

class SignContract(Sign):

    def _update_version_on_signature(self, request_item, version, offer):
        super()._update_version_on_signature(request_item, version, offer)
        if version.country_code != 'BE':
            return
        # Only the applicant/employee has signed
        if request_item.sign_request_id.nb_closed == 1 and version.car_id:
            if version.car_id and version.driver_id != version.employee_id.work_contact_id:
                version.car_id.future_driver_id = version.employee_id.work_contact_id
                version.car_id.plan_to_change_car = False
            if version.bike_id and version.bike_id.driver_id != version.employee_id.work_contact_id:
                version.bike_id.future_driver_id = version.employee_id.work_contact_id
                version.car_id.plan_to_change_bike = False
        # All signers have signed
        if request_item.sign_request_id.nb_wait == 0:
            state_new_request = request.env.ref('fleet.fleet_vehicle_state_new_request', raise_if_not_found=False)
            if version.new_car and not version.ordered_car_id:
                version.ordered_car_id = request.env['fleet.vehicle'].sudo().create({
                    'model_id': version.new_car_model_id.id,
                    'state_id': state_new_request and state_new_request.id,
                    'car_value': version.new_car_model_id.default_car_value,
                    'co2': version.new_car_model_id.default_co2,
                    'co2_emission_unit': version.new_car_model_id.co2_emission_unit,
                    'fuel_type': version.new_car_model_id.default_fuel_type,
                    'acquisition_date': fields.Date.today(),
                    'company_id': version.employee_id.company_id.id,
                    'future_driver_id': version.employee_id.work_contact_id.id
                })

            if version.new_bike_model_id:
                model = version.new_bike_model_id.sudo()
                version.update({
                    'new_bike': False,
                    'new_bike_model_id': False,
                    'transport_mode_bike': True,
                })
                version.bike_id = request.env['fleet.vehicle'].sudo().create({
                    'state_id': state_new_request and state_new_request.id,
                    'future_driver_id': version.employee_id.work_contact_id.id,
                    'company_id': version.company_id.id,
                    'model_id': model.id,
                    'car_value': model.default_car_value,
                    'co2': model.default_co2,
                    'co2_emission_unit': model.co2_emission_unit,
                    'fuel_type': model.default_fuel_type,
                })

class HrContractSalary(main.HrContractSalary):

    def check_access_to_salary_configurator(self, request_token, offer, version):
        has_access, error_page = super().check_access_to_salary_configurator(request_token, offer, version)
        if offer.country_code != 'BE' or not has_access:
            return has_access, error_page

        if version.sudo().l10n_be_time_credit and version.sudo().work_time_rate == 0:
            return False, request.render('http_routing.http_error', {
                'status_code': self.env._('Oops'),
                'status_message': self.env._('This contract is a full time credit time... No simulation can be done for this type of contract as its wage is equal to 0.')})
        return True, None

    @route()
    def onchange_benefit(self, benefit_field, new_value, offer_id, benefits, **kw):
        res = super().onchange_benefit(benefit_field, new_value, offer_id, benefits, **kw)
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
        if offer.country_code != 'BE':
            return res
        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()
            insurance_fields = [
                'insured_relative_children', 'insured_relative_adults',
                'fold_insured_relative_spouse', 'has_hospital_insurance']
            ambulatory_insurance_fields = [
                'l10n_be_ambulatory_insured_children', 'l10n_be_ambulatory_insured_adults',
                'fold_l10n_be_ambulatory_insured_spouse', 'l10n_be_has_ambulatory_insurance']
            if benefit_field == "km_home_work":
                new_value = new_value if new_value else 0
                res['extra_values'] = [
                    ('private_car_reimbursed_amount_manual', new_value),
                    ('l10n_be_bicyle_cost_manual', new_value),
                    ('l10n_be_bicyle_cost', round(request.env['hr.version']._get_private_bicycle_cost(float(new_value)), 2) if benefits['version']['fold_l10n_be_bicyle_cost'] else 0),
                    ('private_car_reimbursed_amount', round(request.env['hr.version']._get_private_car_reimbursed_amount(float(new_value)), 2) if benefits['version']['fold_private_car_reimbursed_amount'] else 0),
                ]
            if benefit_field == 'public_transport_reimbursed_amount':
                new_value = new_value if new_value else 0
                res['new_value'] = round(request.env['hr.version']._get_public_transport_reimbursed_amount(float(new_value)), 2)
            elif benefit_field == 'train_transport_reimbursed_amount':
                new_value = new_value if new_value else 0
                res['new_value'] = round(request.env['hr.version']._get_train_transport_reimbursed_amount(float(new_value)), 2)
            elif benefit_field == 'private_car_reimbursed_amount':
                new_value = new_value if new_value else 0
                res['new_value'] = round(request.env['hr.version']._get_private_car_reimbursed_amount(float(new_value)), 2)
                res['extra_values'] = [
                    ('km_home_work', new_value),
                    ('l10n_be_bicyle_cost_manual', new_value),
                    ('l10n_be_bicyle_cost', round(request.env['hr.version']._get_private_bicycle_cost(float(new_value)), 2) if benefits['version']['fold_l10n_be_bicyle_cost'] else 0),
                ]
            elif benefit_field == 'ip_value':
                res['new_value'] = version.ip_wage_rate if float(new_value) else 0
            elif benefit_field in ['company_car_total_depreciated_cost', 'company_bike_depreciated_cost'] and new_value:
                car_options, vehicle_id = new_value.split('-')
                if car_options == 'new':
                    res['new_value'] = round(request.env['fleet.vehicle.model'].sudo().with_company(version.company_id).browse(int(vehicle_id)).default_total_depreciated_cost, 2)
                else:
                    res['new_value'] = round(request.env['fleet.vehicle'].sudo().with_company(version.company_id).browse(int(vehicle_id)).total_depreciated_cost, 2)
            elif benefit_field == 'wishlist_car_total_depreciated_cost' and new_value:
                res['new_value'] = 0
            elif benefit_field == 'fold_company_car_total_depreciated_cost' and not res['new_value']:
                res['extra_values'] = [('company_car_total_depreciated_cost', 0)]
            elif benefit_field == 'fold_wishlist_car_total_depreciated_cost' and not res['new_value']:
                res['extra_values'] = [('wishlist_car_total_depreciated_cost', 0)]
            elif benefit_field == 'fold_company_bike_depreciated_cost' and not res['new_value']:
                res['extra_values'] = [('company_bike_depreciated_cost', 0)]
            elif benefit_field in insurance_fields:
                child_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.hospital_insurance_amount_child', default=7.2))
                adult_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.hospital_insurance_amount_adult', default=20.5))
                adv = benefits['version']
                child_count = int(adv['insured_relative_children_manual'] or False)
                has_hospital_insurance = float(adv['has_hospital_insurance_radio']) == 1.0 if 'has_hospital_insurance_radio' in adv else False
                adult_count = int(adv['insured_relative_adults_manual'] or False) + int(adv['fold_insured_relative_spouse']) + int(has_hospital_insurance)
                insurance_amount = request.env['hr.version']._get_insurance_amount(child_amount, child_count, adult_amount, adult_count)
                res['extra_values'] = [('has_hospital_insurance', insurance_amount)]
            if benefit_field in ambulatory_insurance_fields:
                child_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.ambulatory_insurance_amount_child', default=7.2))
                adult_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.ambulatory_insurance_amount_adult', default=20.5))
                adv = benefits['version']
                child_count = int(adv['l10n_be_ambulatory_insured_children_manual'] or False)
                l10n_be_has_ambulatory_insurance = float(adv['l10n_be_has_ambulatory_insurance_radio']) == 1.0 if 'l10n_be_has_ambulatory_insurance_radio' in adv else False
                adult_count = int(adv['l10n_be_ambulatory_insured_adults_manual'] or False) \
                            + int(adv['fold_l10n_be_ambulatory_insured_spouse']) \
                            + int(l10n_be_has_ambulatory_insurance)
                insurance_amount = request.env['hr.version']._get_insurance_amount(
                    child_amount, child_count,
                    adult_amount, adult_count)
                res['extra_values'] = [('l10n_be_has_ambulatory_insurance', insurance_amount)]
            if benefit_field == 'l10n_be_bicyle_cost':
                new_value = new_value if new_value else 0
                res['new_value'] = round(request.env['hr.version']._get_private_bicycle_cost(float(new_value)), 2)
                res['extra_values'] = [
                    ('km_home_work', new_value),
                    ('private_car_reimbursed_amount_manual', new_value),
                    ('private_car_reimbursed_amount', round(request.env['hr.version']._get_private_car_reimbursed_amount(float(new_value)), 2) if benefits['version']['fold_private_car_reimbursed_amount'] else 0),
                ]
            if benefit_field == 'fold_l10n_be_bicyle_cost':
                distance = benefits['version_personal']['km_home_work'] or '0'
                res['extra_values'] = [('l10n_be_bicyle_cost', round(request.env['hr.version']._get_private_bicycle_cost(float(distance)), 2) if benefits['version']['fold_l10n_be_bicyle_cost'] else 0)]
            if benefit_field == 'fold_private_car_reimbursed_amount':
                distance = benefits['version_personal']['km_home_work'] or '0'
                res['extra_values'] = [('private_car_reimbursed_amount', round(request.env['hr.version']._get_private_car_reimbursed_amount(float(distance)), 2) if benefits['version']['fold_private_car_reimbursed_amount'] else 0)]
            request.env.flush_all()
            sp.rollback()
        return res

    def _get_default_template_values(self, version, offer):
        values = super()._get_default_template_values(version, offer)
        if version.country_code != 'BE':
            return values
        values['l10n_be_canteen_cost'] = version.l10n_be_canteen_cost
        values['contract_type_id'] = offer.contract_type_id.id
        return values

    def _get_benefits(self, version_vals, offer):
        res = super()._get_benefits(version_vals, offer)
        if offer.country_code != 'BE':
            return res
        display_wishlist = offer.new_car
        if not display_wishlist:
            res -= request.env.ref('l10n_be_hr_contract_salary.l10n_be_transport_new_car')
        return res

    def _get_benefits_values(self, version, offer):
        mapped_benefits, mapped_dependent_benefits, mandatory_benefits, mandatory_benefits_names, benefit_types, dropdown_options, dropdown_group_options, initial_values = super()._get_benefits_values(version, offer)
        if version.country_code != 'BE':
            return mapped_benefits, mapped_dependent_benefits, mandatory_benefits, mandatory_benefits_names, benefit_types, dropdown_options, dropdown_group_options, initial_values
        available_cars = request.env['fleet.vehicle'].sudo().with_company(version.company_id).search(
            version._get_available_vehicles_domain(version.employee_id.work_contact_id)
        ).filtered(lambda car: not car.state_id.hide_in_offer).sorted(key=lambda car: car.total_depreciated_cost)
        available_bikes = request.env['fleet.vehicle'].sudo().with_company(version.company_id).search(
            version._get_available_vehicles_domain(version.employee_id.work_contact_id, vehicle_type='bike')).sorted(key=lambda car: car.total_depreciated_cost)
        force_car = offer.car_id
        force_additional_car = offer.additional_car_ids
        if force_car:
            available_cars |= force_car
            available_cars |= force_additional_car
            version.car_id = force_car
        available_bikes |= version.bike_id

        def generate_dropdown_group_data(available, can_be_requested, only_new, allow_new_cars, vehicle_type='Car'):
            # Creates the necessary data for the dropdown group, looks like this
            # {
            #     'category_name': [
            #         (value, value),
            #         (value, value),...
            #     ],
            #     'other_category': ...
            # }
            model_categories = (available.category_id | available.model_id.category_id | can_be_requested.category_id)
            model_categories_ids = model_categories.sorted(key=lambda c: (c.sequence, c.id)).ids
            model_categories_ids.append(0) # Case when no category
            result = OrderedDict()
            for category in model_categories_ids:
                category_id = model_categories.filtered(lambda c: c.id == category)
                car_values = []
                if not only_new:
                    if not category:  # "No Category"
                        domain = [
                            ('category_id', '=', False),
                            ('model_id.category_id', '=', False),
                        ]
                    else:
                        domain = [
                            '|',
                                ('category_id', '=', category),
                                '&',
                                    ('category_id', '=', False),
                                    ('model_id.category_id', '=', category),
                        ]

                    cars = available.filtered_domain(domain)
                    car_values.extend([(
                        'old-%s' % (car.id),
                        '%s/%s \u2022 %s € \u2022 %s%s%s' % (
                            car.model_id.brand_id.name,
                            car.model_id.name,
                            round(car.total_depreciated_cost, 2),
                            car._get_acquisition_date() if vehicle_type == 'Car' else '',
                            _('\u2022 Available in %s', car.next_assignation_date.strftime('%B %Y')) if car.next_assignation_date else u'',
                            ' \u2022 %s %s' % (car.odometer, ODOMETER_UNITS[car.odometer_unit]) if vehicle_type == 'Car' else '',
                        )
                    ) for car in cars])

                if allow_new_cars:
                    requestables = can_be_requested.filtered_domain([
                        ('category_id', '=', category)
                    ])
                    car_values.extend([(
                        'new-%s' % (model.id),
                        '%s \u2022 %s € \u2022 New %s' % (
                            model.display_name,
                            round(model.default_total_depreciated_cost, 2),
                            vehicle_type,
                        )
                    ) for model in requestables])

                if car_values:
                    result[category_id.name or _("No Category")] = car_values
            return result

        def generate_dropdown_data(available, can_be_requested, only_new_cars, allow_new_cars, vehicle_type='Car'):
            result = []
            if not only_new_cars:
                result.extend([(
                    'old-%s' % (car.id),
                    '%s/%s \u2022 %s € \u2022 %s%s%s' % (
                        car.model_id.brand_id.name,
                        car.model_id.name,
                        round(car.total_depreciated_cost, 2),
                        car._get_acquisition_date() if vehicle_type == 'Car' else '',
                        _('\u2022 Available in %s', car.next_assignation_date.strftime('%B %Y')) if car.next_assignation_date else u'',
                        ' \u2022 %s %s' % (car.odometer, ODOMETER_UNITS[car.odometer_unit]) if vehicle_type == 'Car' else '',
                    )
                ) for car in available])
            if allow_new_cars:
                result.extend([(
                    'new-%s' % (model.id),
                    '%s \u2022 %s € \u2022 New %s' % (
                        model.display_name,
                        round(model.default_total_depreciated_cost, 2),
                        vehicle_type,
                    )
                ) for model in can_be_requested_models])
            return result

        benefits = self._get_benefits(version._get_values_dict(), offer)
        car_benefit = benefits.filtered(
            lambda a: a.res_field_id.name == 'company_car_total_depreciated_cost'
        )
        bike_benefit = benefits.filtered(
            lambda a: a.res_field_id.name == 'company_bike_depreciated_cost'
        )
        wishlist_car_benefit = benefits.filtered(
            lambda a: a.res_field_id.name == 'wishlist_car_total_depreciated_cost'
        )

        # Car stuff
        can_be_requested_models = request.env['fleet.vehicle.model'].sudo().with_company(version.company_id).search(
        version._get_possible_model_domain()).sorted(key=lambda model: model.default_total_depreciated_cost)

        wishlist_new_cars = offer.new_car
        allow_new_cars = False

        if car_benefit.display_type == 'dropdown-group':
            dropdown_group_options['company_car_total_depreciated_cost'] = \
                generate_dropdown_group_data(available_cars, can_be_requested_models, False, allow_new_cars)
        else:
            dropdown_options['company_car_total_depreciated_cost'] = \
                generate_dropdown_data(available_cars, can_be_requested_models, False, allow_new_cars)

        if wishlist_new_cars:
            if wishlist_car_benefit.display_type == 'dropdown-group':
                dropdown_group_options['wishlist_car_total_depreciated_cost'] = \
                    generate_dropdown_group_data(available_cars, can_be_requested_models, True, True)
            else:
                dropdown_options['wishlist_car_total_depreciated_cost'] = \
                    generate_dropdown_data(available_cars, can_be_requested_models, True, True)
            initial_values['fold_wishlist_car_total_depreciated_cost'] = False
            initial_values['wishlist_car_total_depreciated_cost'] = 0

        # Bike stuff
        can_be_requested_models = request.env['fleet.vehicle.model'].sudo().with_company(version.company_id).search(
        version._get_possible_model_domain(vehicle_type='bike')).sorted(key=lambda model: model.default_total_depreciated_cost)
        if bike_benefit.display_type == 'dropdown-group':
            dropdown_group_options['company_bike_depreciated_cost'] = \
                generate_dropdown_group_data(available_bikes, can_be_requested_models, False, True, 'Bike')
        else:
            dropdown_options['company_bike_depreciated_cost'] = \
                generate_dropdown_data(available_bikes, can_be_requested_models, False, True, 'Bike')

        if force_car:
            initial_values['select_company_car_total_depreciated_cost'] = 'old-%s' % force_car.id
            initial_values['fold_company_car_total_depreciated_cost'] = True
            initial_values['company_car_total_depreciated_cost'] = force_car.total_depreciated_cost
        elif version.car_id:
            initial_values['select_company_car_total_depreciated_cost'] = 'old-%s' % version.car_id.id
            initial_values['fold_company_car_total_depreciated_cost'] = True
            initial_values['company_car_total_depreciated_cost'] = version.car_id.total_depreciated_cost
        else:
            initial_values['fold_company_car_total_depreciated_cost'] = False
        if version.bike_id:
            initial_values['select_company_bike_depreciated_cost'] = 'old-%s' % version.bike_id.id
        elif version.new_bike_model_id:
            initial_values['select_company_bike_depreciated_cost'] = 'new-%s' % version.new_bike_model_id.id

        hospital_insurance_child_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.hospital_insurance_amount_child', default=7.2))
        hospital_insurance_adult_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.hospital_insurance_amount_adult', default=20.5))
        ambulatory_insurance_child_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.ambulatory_insurance_amount_child', default=7.2))
        ambulatory_insurance_adult_amount = float(request.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.ambulatory_insurance_amount_adult', default=20.5))

        hospital_insurance_child_count = version.insured_relative_children
        hospital_insurance_adult_count = version.insured_relative_adults_total
        ambulatory_insurance_child_count = version.l10n_be_ambulatory_insured_children
        ambulatory_insurance_adult_count = version.l10n_be_ambulatory_insured_adults_total

        hospital_insurance_amount = request.env['hr.version']._get_insurance_amount(
            hospital_insurance_child_amount, hospital_insurance_child_count,
            hospital_insurance_adult_amount, hospital_insurance_adult_count)
        ambulatory_insurance_amount = request.env['hr.version']._get_insurance_amount(
            ambulatory_insurance_child_amount, ambulatory_insurance_child_count,
            ambulatory_insurance_adult_amount, ambulatory_insurance_adult_count)

        initial_values['has_hospital_insurance'] = hospital_insurance_amount
        initial_values['l10n_be_has_ambulatory_insurance'] = ambulatory_insurance_amount

        return mapped_benefits, mapped_dependent_benefits, mandatory_benefits, mandatory_benefits_names, benefit_types, dropdown_options, dropdown_group_options, initial_values

    def _get_new_version_values(self, version_vals, employee, benefits, offer):
        res = super()._get_new_version_values(version_vals, employee, benefits, offer)
        if offer.country_code != 'BE':
            return res
        fields_to_copy = [
            'has_laptop', 'work_time_rate',
            'rd_percentage', 'no_onss', 'no_withholding_taxes', 'meal_voucher_amount',
        ]
        for field_to_copy in fields_to_copy:
            if field_to_copy in version_vals:
                res[field_to_copy] = version_vals.get(field_to_copy)
        res['has_hospital_insurance'] = float(benefits['has_hospital_insurance_radio']) == 1.0 if 'has_hospital_insurance_radio' in benefits else False
        res['l10n_be_has_ambulatory_insurance'] = float(benefits['l10n_be_has_ambulatory_insurance_radio']) == 1.0 if 'l10n_be_has_ambulatory_insurance_radio' in benefits else False
        res['l10n_be_canteen_cost'] = benefits['l10n_be_canteen_cost'] if 'l10n_be_canteen_cost' in benefits else False
        res['ip'] = bool(benefits['ip_value_radio']) if 'ip_value_radio' in benefits else False
        res['ip_wage_rate'] = benefits['ip_value'] if 'ip_value' in benefits else 0
        return res

    def create_new_version(self, version_vals, offer_id, benefits, no_write=False, **kw):
        new_version, version_diff = super().create_new_version(version_vals, offer_id, benefits, no_write=no_write, **kw)
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id).exists()
        if offer.country_code != 'BE':
            return new_version, version_diff
        if new_version.l10n_be_time_credit:
            new_version.date_end = version_vals.get('date_end')
        if new_version.car_id.id != version_vals.get('car_id'):
            # If the chosen car is different from the one in the current version, add the car model name to the diff
            car = self.env['fleet.vehicle'].sudo().browse(version_vals.get('car_id'))
            version_diff.append((_('Company Car'), car.display_name or '', new_version.car_id.display_name or ''))
        if kw.get('package_submit', False):
            # If the chosen existing car is already taken by someone else (for example if the
            # window was open for a long time)
            if new_version.transport_mode_car and new_version.car_id:
                # In case in the car was reserved for the applicant
                partner_ids = offer.applicant_id.partner_id | new_version.employee_id.work_contact_id
                available_cars_domain = new_version._get_available_vehicles_domain(partner_ids)
                is_selected_car_available = request.env['fleet.vehicle'].sudo().search_count([('id', '=', new_version.car_id.id)] + available_cars_domain, limit=1)
                if not is_selected_car_available and new_version.car_id != offer.car_id:
                    return {'error': True, 'error_msg': _("Sorry, the selected car has been selected by someone else. Please refresh and try again.")}

            return new_version, version_diff

        if new_version.new_car and kw.get('wishlist_simulation'):
            employee = new_version.employee_id
            model = request.env['fleet.vehicle.model'].sudo().with_company(new_version.company_id).browse(int(new_version.new_car_model_id))
            state_new_request = request.env.ref('fleet.fleet_vehicle_state_new_request', raise_if_not_found=False)
            new_version.car_id = request.env['fleet.vehicle'].sudo().with_company(new_version.company_id).create({
                'model_id': model.id,
                'state_id': state_new_request and state_new_request.id,
                'driver_id': employee.work_contact_id.id,
                'car_value': model.default_car_value,
                'co2': model.default_co2,
                'co2_emission_unit': model.co2_emission_unit,
                'fuel_type': model.default_fuel_type,
                'company_id': new_version.company_id.id,
            })
        return new_version, version_diff

    def _get_wage_to_apply(self):
        return "l10n_be_wage_with_mobility_budget"

    def _get_compute_results(self, new_version):
        result = super()._get_compute_results(new_version)
        if new_version.structure_type_id != self.env.ref('hr.structure_type_employee_cp200', raise_if_not_found=False):
            return result
        result['double_holiday_wage'] = round(new_version.double_holiday_wage, 2)
        wage_to_apply = self._get_wage_to_apply()
        # Horrible hack: Add a sequence / display condition fields on salary resume model in master
        yearly_benefits = result['resume_lines_mapped']['Yearly Benefits']
        if yearly_benefits:
            annual_time_off = yearly_benefits['annual_time_off']
            annual_time_off_list = list(annual_time_off)
            annual_time_off_list[3] = _('20 days are the maximum amount an employee could get if she/he worked on a full working rate during the previous year in Belgium')
            result['resume_lines_mapped']['Yearly Benefits']['annual_time_off'] = tuple(annual_time_off_list)

        resume = result['resume_lines_mapped']['Monthly Salary']
        if 'SALARY' in resume and resume.get(wage_to_apply) and resume[wage_to_apply][1] != resume['SALARY'][1]:
            ordered_fields = [wage_to_apply, 'SALARY', 'NET']
            if new_version.env.context.get('simulation_working_schedule', '100') != '100':
                salary_tuple = result['resume_lines_mapped']['Monthly Salary']['SALARY']
                salary_tuple = (_('Gross (Part Time)'), *salary_tuple[1:])
                result['resume_lines_mapped']['Monthly Salary']['SALARY'] = salary_tuple
        else:
            ordered_fields = [wage_to_apply, 'NET']
        result['resume_lines_mapped']['Monthly Salary'] = {field: resume.get(field, 0) for field in ordered_fields}
        result['l10n_be_mobility_budget_amount_monthly'] = new_version.l10n_be_mobility_budget_amount_monthly
        result['l10n_be_wage_with_mobility_budget'] = new_version.l10n_be_wage_with_mobility_budget

        return result

    @route('/salary_package/update_salary', type="jsonrpc")
    def update_salary(self, offer_id=None, benefits=None, **kw):
        result = super().update_salary(offer_id, benefits, **kw)
        wishlist_result = {}
        offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
        if offer.country_code != 'BE':
            return result
        request.env.flush_all()
        with request.env.cr.savepoint(flush=False) as sp:
            version = offer._get_version()

            offer = request.env['hr.contract.salary.offer'].sudo().browse(offer_id)
            minimum_gross_wage = request.env['hr.rule.parameter'].sudo()._get_parameter_from_code(
                'cp200_min_gross_wage', offer.contract_start_date, raise_if_not_found=False)

            if result.get('l10n_be_wage_with_mobility_budget', False):
                gross_to_compare = result['l10n_be_wage_with_mobility_budget']
            else:
                gross_to_compare = result['new_gross']

            if minimum_gross_wage and gross_to_compare < minimum_gross_wage and offer.country_code == 'BE':
                result['configurator_warning'] = _("Your monthly gross wage is below the minimum legal amount %(min_gross)s €", min_gross=minimum_gross_wage)

            if benefits['version'].get('fold_wishlist_car_total_depreciated_cost', False) and 'wishlist_car_total_depreciated_cost' in benefits['version']:
                benefits['version'].update({
                    'fold_company_car_total_depreciated_cost': True,
                    'company_car_total_depreciated_cost': benefits['version']['wishlist_car_total_depreciated_cost'],
                    'select_company_car_total_depreciated_cost': benefits['version']['select_wishlist_car_total_depreciated_cost'],
                })

                version_vals = version._get_values_dict()
                new_version = self.create_new_version(version_vals, offer_id, benefits, wishlist_simulation=True)[0]
                final_yearly_costs = float(benefits['version']['final_yearly_costs'] or 0.0)
                new_gross = new_version._get_gross_from_employer_costs(final_yearly_costs)
                new_version.write({
                    'wage': new_gross,
                    'final_yearly_costs': final_yearly_costs,
                })
                wishlist_result['new_gross'] = round(new_gross, 2)
                new_version = new_version.with_context(
                    origin_version_id=version.id,
                    simulation_working_schedule=kw.get('simulation_working_schedule', False))
                wishlist_result.update(self._get_compute_results(new_version))

                result['wishlist_simulation'] = wishlist_result
                if minimum_gross_wage and new_gross < minimum_gross_wage:
                    result['wishlist_warning'] = _("Your monthly gross wage will be below the minimum legal amount %(min_gross)s €", min_gross=minimum_gross_wage)

            request.env.flush_all()
            sp.rollback()
        return result

    # TODO check this
    def _generate_payslip(self, new_version):
        payslip = super()._generate_payslip(new_version)
        if new_version.country_code != 'BE':
            return payslip
        if new_version.car_id:
            payslip.vehicle_id = new_version.car_id
        if new_version.commission_on_target:
            payslip.input_line_ids = [(0, 0, {
                'input_type_id': request.env.ref('l10n_be_hr_payroll.input_fixed_commission').id,
                'amount': new_version.commission_on_target,
            })]
        if new_version.l10n_be_bicyle_cost:
            payslip.input_line_ids = [(0, 0, {
                'input_type_id': request.env.ref('l10n_be_hr_payroll.cp200_input_cycle_transportation').id,
                'amount': 4,  # Considers cycling one day per week
            })]
        return payslip

    def _get_payslip_line_values(self, payslip, codes):
        res = super()._get_payslip_line_values(payslip, codes + ['BASIC', 'COMMISSION'])
        if payslip.country_code != 'BE':
            return res
        res['SALARY'][payslip.id]['total'] = res['BASIC'][payslip.id]['total'] + res['COMMISSION'][payslip.id]['total']
        return res

    def _get_personal_infos_langs(self, version, personal_info):
        active_langs = super()._get_personal_infos_langs(version, personal_info)
        if version.country_code != 'BE':
            return active_langs
        personal_info_lang = request.env.ref('l10n_be_hr_contract_salary.hr_contract_salary_personal_info_lang')
        if version._is_struct_from_country('BE') and personal_info == personal_info_lang:
            belgian_langs = active_langs.filtered(lambda l: l.code in ["fr_BE", "fr_FR", "nl_BE", "nl_NL", "de_BE", "de_DE"])
            return active_langs if not belgian_langs else belgian_langs
        return active_langs
