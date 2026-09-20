from odoo import api, fields, models
from odoo.fields import Domain


class HrVersion(models.Model):
    _inherit = 'hr.version'

    @api.model
    def _get_available_vehicles_domain(self, driver_ids=None, vehicle_type='car'):
        domain = Domain.AND([
            Domain.OR([
                [('company_id', '=', False)],
                [('company_id', '=', self.company_id.id)],
            ]),
            [('model_id.vehicle_type', '=', vehicle_type)],
            Domain.OR([
                [(f'plan_to_change_{vehicle_type}', '=', True)],
                [('future_driver_id', 'in', driver_ids.ids if driver_ids else [])],
            ]),
            [('write_off_date', '=', False)],
        ])
        waiting_stage = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
        if waiting_stage:
            domain = Domain('state_id', '!=', waiting_stage.id) & domain
        return domain

    @api.model
    def _get_vehicles_without_current_drivers_domain(self, driver_ids=None, vehicle_type='car'):
        """
            This domain is identical to the one in _get_available_vehicles_domain. The difference is
            that it excludes vehicles that have a driver currently even if the current driver is the
            employee under the contract or the current driver plans to change the car in the future.
        """
        domain = Domain([
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
            '|', ('future_driver_id', '=', False), ('future_driver_id', 'in', driver_ids.ids),
            ('model_id.vehicle_type', '=', vehicle_type),
            ('driver_id', '=', False),
            ('write_off_date', '=', False),
        ])
        waiting_stage = self.env.ref('fleet.fleet_vehicle_state_waiting_list', raise_if_not_found=False)
        if waiting_stage:
            domain = Domain('state_id', '!=', waiting_stage.id) & domain
        return domain

    def _get_possible_model_domain(self, vehicle_type='car'):
        return [('can_be_requested', '=', True), ('vehicle_type', '=', vehicle_type)]

    car_id = fields.Many2one(
        'fleet.vehicle', string='Company Car',
        tracking=True, compute="_compute_car_id", store=True, readonly=False,
        domain=lambda self: [('company_id', 'in', (False, self.env.company.id)), ('vehicle_type', '=', 'car')],
        groups='fleet.fleet_group_manager,hr.hr_group_user')
    car_atn = fields.Float(
        compute='_compute_car_atn_and_costs',
        store=True,
        compute_sudo=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    wishlist_car_total_depreciated_cost = fields.Float(
        compute='_compute_car_atn_and_costs', store=True, compute_sudo=True, groups="hr_payroll.group_hr_payroll_user")
    company_car_total_depreciated_cost = fields.Float(
        compute='_compute_car_atn_and_costs',
        store=True,
        compute_sudo=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    available_cars_amount = fields.Integer(
        compute='_compute_available_cars_amount',
        string='Number of available cars',
        groups="hr.group_hr_user",
        compute_sudo=True)
    new_car = fields.Boolean('Requested a new car', groups="hr.group_hr_user", tracking=True)
    ordered_car_id = fields.Many2one('fleet.vehicle', string='Ordered New Car',
        tracking=True, store=True, readonly=False,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('vehicle_type', '=', 'car')]",
        groups='fleet.fleet_group_manager,hr.hr_group_user')
    new_car_model_id = fields.Many2one(
        'fleet.vehicle.model', string="New Company Car", domain=lambda self: self._get_possible_model_domain(),
        groups='hr.group_hr_user', tracking=True)
    # Useful on sign to use only one box to sign the contract instead of 2
    car_model_name = fields.Char(compute='_compute_car_model_name', compute_sudo=True,
                                 groups='hr.group_hr_user')
    max_unused_cars = fields.Integer(compute='_compute_max_unused_cars', groups='hr.group_hr_user')
    acquisition_date = fields.Date(related='car_id.acquisition_date', readonly=False, groups="fleet.fleet_group_manager")
    car_value = fields.Float(related="car_id.car_value", readonly=False, groups="fleet.fleet_group_manager")
    fuel_type = fields.Selection(selection=lambda self: self.env['fleet.vehicle']._fields['fuel_type']._description_selection(self.env), compute="_compute_fuel_type", readonly=False, groups="fleet.fleet_group_manager")
    co2 = fields.Float(related="car_id.co2", readonly=False, groups="fleet.fleet_group_manager")
    driver_id = fields.Many2one('res.partner', related="car_id.driver_id", readonly=False, groups="fleet.fleet_group_manager")
    car_open_contracts_count = fields.Integer(compute='_compute_car_open_contracts_count', groups="fleet.fleet_group_manager")
    recurring_cost_amount_depreciated = fields.Float(
        groups="fleet.fleet_group_manager",
        compute='_compute_recurring_cost_amount_depreciated',
        inverse="_inverse_recurring_cost_amount_depreciated", tracking=True)
    transport_mode_bike = fields.Boolean('Uses Bike', groups='hr.group_hr_user', tracking=True)
    bike_id = fields.Many2one(
        'fleet.vehicle', string="Company Bike",
        tracking=True,
        compute='_compute_bike_id', store=True, readonly=False,
        domain=lambda self: [('company_id', 'in', (False, self.env.company.id)), ('vehicle_type', '=', 'bike')],
        groups='fleet.fleet_group_manager')
    company_bike_depreciated_cost = fields.Float(
        compute='_compute_company_bike_depreciated_cost', store=True, compute_sudo=True,
        groups='hr.group_hr_user')
    new_bike = fields.Boolean(
        'Requested a new bike', compute='_compute_new_bike', store=True, readonly=False,
        groups='hr.group_hr_user')
    new_bike_model_id = fields.Many2one(
        'fleet.vehicle.model', string="New Bike",
        domain=lambda self: self._get_possible_model_domain(vehicle_type='bike'),
        compute='_compute_new_bike_model_id', store=True, readonly=False, groups='hr.group_hr_user')
    transport_mode_private_car = fields.Boolean(store=True, readonly=False)

    @api.depends('new_bike', 'new_bike_model_id')
    def _compute_bike_id(self):
        for version in self:
            if version.new_bike or version.new_bike_model_id:
                version.bike_id = False

    @api.depends('bike_id')
    def _compute_new_bike_model_id(self):
        for version in self:
            if version.bike_id:
                version.update({
                    'new_bike_model_id': False,
                    'new_bike': False,
                })

    @api.depends('new_bike_model_id')
    def _compute_new_bike(self):
        for version in self:
            if version.new_bike_model_id:
                version.new_bike = True

    @api.depends('car_id')
    def _compute_car_model_name(self):
        for version in self:
            if version.car_id:
                version.car_model_name = version.car_id.model_id.display_name
            else:
                version.car_model_name = False

    @api.depends('employee_id', 'transport_mode_private_car')
    def _compute_car_id(self):
        versions_to_reset = self.filtered(lambda c: c.transport_mode_private_car or not c.transport_mode_car)
        versions_to_reset.car_id = False
        remaining_versions = self - versions_to_reset
        if not remaining_versions:
            return
        employees_partners = remaining_versions.employee_id.work_contact_id
        cars = self.env['fleet.vehicle'].search([
            ('vehicle_type', '=', 'car'),
            '|', ('driver_id', 'in', employees_partners.ids), ('future_driver_id', 'in', employees_partners.ids)
        ], order='future_driver_id, driver_id')
        dict_car = {
            (car.driver_id or car.future_driver_id).id: car.id for car in cars
        }
        for version in remaining_versions:
            if version.car_id:
                continue
            partner_id = version.employee_id.work_contact_id.id
            if partner_id in dict_car:
                version.car_id = dict_car[partner_id]
                version.transport_mode_car = True
            else:
                version.car_id = False

    @api.depends('car_id')
    def _compute_fuel_type(self):
        for version in self:
            version.fuel_type = version.car_id.fuel_type if version.car_id else False

    @api.depends('car_id', 'car_id.total_depreciated_cost', 'car_id.atn')
    def _compute_car_atn_and_costs(self):
        self.car_atn = False
        self.company_car_total_depreciated_cost = False
        for version in self:
            if version.car_id:
                version.car_atn = version.car_id.atn
                version.company_car_total_depreciated_cost = version.car_id.total_depreciated_cost

    @api.depends('new_bike', 'bike_id', 'new_bike_model_id', 'bike_id.total_depreciated_cost',
        'bike_id.co2_fee', 'new_bike_model_id.default_total_depreciated_cost', 'transport_mode_bike')
    def _compute_company_bike_depreciated_cost(self):
        for version in self:
            version.company_bike_depreciated_cost = False
            if not version.new_bike and version.transport_mode_bike and version.bike_id:
                version.company_bike_depreciated_cost = version.bike_id.total_depreciated_cost
            elif not version.transport_mode_bike and version.new_bike and version.new_bike_model_id:
                version.company_bike_depreciated_cost = version.new_bike_model_id.default_recurring_cost_amount_depreciated

    @api.depends('car_id.log_contracts.state')
    def _compute_car_open_contracts_count(self):
        for version in self:
            version.car_open_contracts_count = len(version.car_id.log_contracts.filtered(
                lambda c: c.state == 'open').ids)

    @api.depends('car_open_contracts_count', 'car_id.log_contracts.recurring_cost_amount_depreciated')
    def _compute_recurring_cost_amount_depreciated(self):
        for version in self:
            if version.car_open_contracts_count == 1:
                version.recurring_cost_amount_depreciated = version.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated
            else:
                version.recurring_cost_amount_depreciated = 0.0

    def _inverse_recurring_cost_amount_depreciated(self):
        for version in self:
            if version.car_open_contracts_count == 1:
                version.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated = version.recurring_cost_amount_depreciated

    def _get_available_cars_domain(self):
        return self._get_vehicles_without_current_drivers_domain(
            self.employee_id.work_contact_id,
        )

    @api.depends('name')
    def _compute_available_cars_amount(self):
        for version in self:
            version.available_cars_amount = self.env['fleet.vehicle'].sudo().search_count(
                version._get_available_cars_domain(),
            )

    @api.depends('name')
    def _compute_max_unused_cars(self):
        params = self.env['ir.config_parameter'].sudo()
        max_unused_cars = params.get_param('l10n_be_hr_payroll_fleet.max_unused_cars', default=5)
        for version in self:
            version.max_unused_cars = 999999 if version.env.context.get('is_applicant') else int(max_unused_cars)

    @api.onchange('new_bike')
    def _onchange_new_bike(self):
        if self.new_bike:
            self.bike_id = False
            self.transport_mode_bike = False
        else:
            self.new_bike_model_id = False

    @api.onchange('transport_mode_bike', 'transport_mode_train', 'transport_mode_public', 'transport_mode_car')
    def _onchange_transport_mode(self):
        super()._onchange_transport_mode()
        if self.transport_mode_bike:
            self.new_bike = False
            self.new_bike_model_id = False
        else:
            self.bike_id = False
        if self.transport_mode_car:
            self.has_bicycle = False
        if self.sudo().car_id:
            self.transport_mode_private_car = False

    @api.onchange('has_bicycle')
    def _onchange_has_bicycle(self):
        if self.has_bicycle:
            self.transport_mode_car = False
            self.car_id = False

    def write(self, vals):
        # Force to track cars in employee form if any changes is found after version write
        if not self.env.context.get('tracking_disable'):
            self.employee_id._track_prepare(["car_id", "ordered_car_id", "bike_id"])
        return super().write(vals=vals)

    def _get_fields_that_recompute_payslip(self):
        # Returns the fields that should recompute the payslip
        return super()._get_fields_that_recompute_payslip() + [
            'car_id',
        ]
