from odoo import api, fields, models


class EsgEmissionFactor(models.Model):
    _name = 'esg.emission.factor'
    _description = 'Emission Factor'
    _inherit = [
        'mail.thread',
    ]

    name = fields.Char(required=True)
    sequence = fields.Integer()
    active = fields.Boolean(default=True)

    code = fields.Char(string="Code", index=True)  # required=True

    esg_emissions_value = fields.Float(compute='_compute_esg_emissions_value', string='Emissions (kgCO₂e)', store=True, readonly=False, tracking=True)
    source_id = fields.Many2one('esg.emission.source', required=True)
    scope = fields.Selection(related='source_id.scope')
    scope_complete_name = fields.Char(related='source_id.complete_name')
    company_id = fields.Many2one('res.company')

    valid_from = fields.Date()
    valid_to = fields.Date()

    esg_uncertainty_value = fields.Float(string="Uncertainty (%)")
    compute_method = fields.Selection(selection=[
            ('physically', 'Physically (Quantity)'),
            ('monetary', 'Monetary'),
        ],
        required=True,
        default='physically',
    )
    unit_name = fields.Char(compute='_compute_unit_name')
    database_id = fields.Many2one('esg.database')
    gas_line_ids = fields.One2many('esg.emission.factor.line', 'esg_emission_factor_id', tracking=True)
    assignation_line_ids = fields.One2many('esg.assignation.line', 'esg_emission_factor_id')
    description = fields.Html()
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', compute='_compute_uom_id', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', store=True, readonly=False)
    activity_type_ids = fields.Many2many('esg.activity.type', string='Activity Types', compute='_compute_activity_type_ids', store=True)
    account_move_line_ids = fields.One2many('account.move.line', 'esg_emission_factor_id')
    esg_other_emission_ids = fields.One2many('esg.other.emission', 'esg_emission_factor_id')
    nb_linked_emissions = fields.Integer(compute='_compute_nb_linked_emissions')
    region = fields.Char('Region / Regional Conditions')

    @api.depends('uom_id', 'currency_id', 'compute_method')
    def _compute_unit_name(self):
        for factor in self:
            if factor.compute_method == 'monetary':
                factor.unit_name = factor.currency_id.name
            else:
                factor.unit_name = factor.uom_id.name

    @api.depends('gas_line_ids.esg_emissions_value')
    def _compute_esg_emissions_value(self):
        for factor in self:
            factor.esg_emissions_value = sum(factor.gas_line_ids.mapped('esg_emissions_value'))

    @api.depends('compute_method')
    def _compute_uom_id(self):
        for factor in self:
            if factor.compute_method == 'monetary':
                factor.uom_id = False

    @api.depends('compute_method')
    def _compute_currency_id(self):
        for factor in self:
            if factor.compute_method == 'physically':
                factor.currency_id = False

    @api.depends('gas_line_ids.activity_type_id')
    def _compute_activity_type_ids(self):
        for factor in self:
            factor.activity_type_ids = factor.gas_line_ids.activity_type_id

    @api.depends('account_move_line_ids', 'esg_other_emission_ids')
    def _compute_nb_linked_emissions(self):
        for factor in self:
            factor.nb_linked_emissions = len(
                factor.account_move_line_ids.filtered(lambda aml: aml.parent_state == 'posted'),
            ) + len(factor.esg_other_emission_ids)

    def action_open_linked_emissions(self):
        self.ensure_one()
        return {
            'name': self.env._("Emissions using %(emission_factor)s", emission_factor=self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,kanban,graph,pivot',
            'res_model': 'esg.carbon.emission.report',
            'domain': [('esg_emission_factor_id', '=', self.id)],
        }
