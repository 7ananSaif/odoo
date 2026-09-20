from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EsgGas(models.Model):
    _name = 'esg.gas'
    _description = 'Gas'

    name = fields.Char(translate=True, required=True)
    sequence = fields.Integer(default=10)
    global_warming_potential = fields.Integer(
        string='Global Warming Potential (GWP)', required=True, aggregator='avg',
        help='Relative impact of gas on global warming compared to CO₂ over 100 years'
    )
    category = fields.Selection([
        ('co2', 'Carbon Dioxide (CO₂)'),
        ('ch4', 'Methane (CH₄)'),
        ('n2o', 'Nitrous Oxide (N₂O)'),
        ('hfc', 'Hydrofluorocarbons (HFCs)'),
        ('pfc', 'Perfluorocarbons (PFCs)'),
        ('sf6', 'Sulfur Hexafluoride (SF₆)'),
        ('nf3', 'Nitrogen Trifluoride'),
        ('other', 'Other Halogenated substances'),
        ('precursors', 'Precursors'),
    ])
    code = fields.Char(string='Code', required=True, help='Unique code identifying the gas')
    is_mandatory_gas = fields.Boolean(compute='_compute_is_mandatory_gas')

    _code_unique = models.Constraint(
        'unique(code)',
        'The code of a gas must be unique.',
    )

    _non_null_gwp = models.Constraint(
        'CHECK(global_warming_potential != 0)',
        'Global Warming Potential (GWP) cannot be equal to 0.',
    )

    def _get_mandatory_gases_codes(self):
        return (
            'co2',
            'ch4f',
            'ch4b',
            'n2o',
            'hfc_134a',
            'hfc_23',
            'hfc_152a',
            'cf4',
            'c2f6',
            'sf6',
        )

    def _compute_is_mandatory_gas(self):
        mandatory_gases_codes = self._get_mandatory_gases_codes()
        for gas in self:
            gas.is_mandatory_gas = gas.code in mandatory_gases_codes

    @api.ondelete(at_uninstall=False)
    def _prevent_data_deletion(self):
        mandatory_gases = self.filtered(lambda gas: gas.is_mandatory_gas)
        if mandatory_gases:
            raise ValidationError(self.env._(
                "Some gases you're trying to delete are used for data imports:\n%(gases)s",
                gases='\n'.join(gas.name for gas in mandatory_gases),
            ))
