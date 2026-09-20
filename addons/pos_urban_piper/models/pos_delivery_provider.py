from odoo import api, fields, models


class PosDeliveryProvider(models.Model):
    _name = 'pos.delivery.provider'
    _description = 'Online Delivery Providers'
    _inherit = ['pos.load.mixin']

    name = fields.Char(string='Name', required=True, help='Name of the delivery provider i.e. Zomato, UberEats, etc.')
    technical_name = fields.Char(string='Provider Name', help='Technical name of the provider used by UrbanPiper')
    image_128 = fields.Image(string='Provider Image', max_width=128, max_height=128)
    journal_code = fields.Char(
        string='Journal Short Code',
        help='Short code of the journal to be used for journal creation'
    )
    available_country_ids = fields.Many2many(
        'res.country',
        string='Available Countries',
        help='Countries where this provider is available'
    )

    _technical_name_uniq = models.Constraint(
        'unique(technical_name)',
        "Provider Name must be unique.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'name', 'technical_name']

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['id']
