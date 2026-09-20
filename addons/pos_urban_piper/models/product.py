from odoo import api, fields, models, Command, _
from collections import defaultdict
from .pos_urban_piper_request import UrbanPiperClient


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    urbanpiper_pos_config_ids = fields.Many2many(
        'pos.config',
        string='Available on Food Delivery',
        help='Check this if the product is available for food delivery.',
        domain="[('urbanpiper_store_identifier', '!=', False), ('module_pos_urban_piper', '=', True)]",
    )
    urbanpiper_pos_platform_ids = fields.Many2many(
        'pos.delivery.provider',
        string='Available on',
        help='Check this if the product is available for following platform.',
        compute='_compute_urbanpiper_pos_platform_ids',
        store=True,
        readonly=False,
    )
    urbanpiper_meal_type = fields.Selection([
        ('1', 'Vegetarian'),
        ('2', 'Non-Vegetarian'),
        ('3', 'Eggetarian'),
        ('4', 'N/A')], string='Meal Type', required=True, default='4', help='Product type i.e. Veg, Non-Veg, etc.')
    is_recommended_on_urbanpiper = fields.Boolean(string='Is Recommended', help='Recommended products on food platforms.')
    urban_piper_status_ids = fields.One2many(
        'product.urban.piper.status',
        'product_tmpl_id',
        string='Stores',
        help='Handle products with urban piper and pos config - Product is linked or not with appropriate store.'
    )
    is_alcoholic_on_urbanpiper = fields.Boolean(string='Is Alcoholic', help='Indicates if the product contains alcohol.')

    @api.depends('urbanpiper_pos_config_ids')
    def _compute_urbanpiper_pos_platform_ids(self):
        for record in self:
            record.urbanpiper_pos_platform_ids = [Command.set(record.sudo().urbanpiper_pos_config_ids.urbanpiper_delivery_provider_ids.ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields += ['urbanpiper_pos_config_ids']
        return fields

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        if not config.module_pos_urban_piper:
            return read_records
        synced_product_ids = records.urban_piper_status_ids.filtered(lambda s: s.config_id == config and s.is_product_linked).product_tmpl_id.ids
        for product in read_records:
            product['_synced_on_urbanpiper'] = product['id'] in synced_product_ids
        return read_records

    def write(self, vals):
        field_list = ['name', 'description', 'list_price', 'weight', 'urbanpiper_meal_type', 'pos_categ_ids', 'image_1920', 'public_description',
                    'product_template_attribute_value_ids', 'taxes_id', 'is_recommended_on_urbanpiper', 'is_alcoholic_on_urbanpiper', 'attribute_line_ids', 'urbanpiper_pos_platform_ids']
        if any(field in vals for field in field_list):
            urban_piper_statuses = self.urban_piper_status_ids.filtered(lambda s: s.is_product_linked)
            urban_piper_statuses.write({'is_product_linked': False})
        # Enable/Disable product on Urban Piper based on pos_config_ids changes.
        products_has_config_before_write = {p.id: p.urbanpiper_pos_config_ids for p in self.sudo()}
        res = super().write(vals)
        if self.env.context.get('from_pos_ui', False):
            return res
        products_has_config_after_write = {p.id: p.urbanpiper_pos_config_ids for p in self.sudo()}
        configs_to_enable = defaultdict(list)
        configs_to_disable = defaultdict(list)
        for p in self:
            for config in products_has_config_after_write[p.id] - products_has_config_before_write[p.id]:
                if config in p.urban_piper_status_ids.config_id:
                    configs_to_enable[config].append(p)
            for config in products_has_config_before_write[p.id] - products_has_config_after_write[p.id]:
                if config in p.urban_piper_status_ids.config_id:
                    configs_to_disable[config].append(p)
        for config, products in configs_to_enable.items():
            up = UrbanPiperClient(config)
            up.register_item_toggle(products, True)
        for config, products in configs_to_disable.items():
            up = UrbanPiperClient(config)
            up.register_item_toggle(products, False)
        return res

    def toggle_product_food_delivery_availability(self, config_id):
        """
        Toggle a product's availability on the UrbanPiper. (if product is synced)
        """
        self.ensure_one()
        if not self.urban_piper_status_ids.filtered(lambda s: s.config_id.id == config_id):
            return {
                'status': 'fail',
                'error': _('"%s" is not synchronized with the UrbanPiper. Please sync it before proceeding.', self.name)
            }
        status = config_id not in self.urbanpiper_pos_config_ids.ids
        config = self.env['pos.config'].browse(config_id)
        up = UrbanPiperClient(config)
        toggle_response = up.register_item_toggle(self, status)
        if toggle_response.get('status') != 'success':
            return {
                'status': toggle_response.get('status'),
                'error': next(iter(toggle_response.get('errors', {}).values()), '')
            }
        if status:
            self.urbanpiper_pos_config_ids |= config
        else:
            self.urbanpiper_pos_config_ids -= config
        return toggle_response
