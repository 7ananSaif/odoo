from odoo import fields, models, api, _
from odoo.exceptions import AccessError, ValidationError


class PosPrepDisplay(models.Model):
    _name = 'pos.prep.display'
    _description = 'Pos Preparation Display'
    _inherit = ["pos.bus.mixin", "pos.load.mixin"]

    name = fields.Char("Name", required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    pos_config_ids = fields.Many2many(string="Point of Sale", comodel_name='pos.config')
    category_ids = fields.Many2many('pos.category', string="Product categories", help="Product categories that will be displayed on this screen.")
    order_count = fields.Integer("Order count", compute='_compute_order_count')
    average_time = fields.Integer("Order average time", compute='_compute_order_count', help="Average time of all order that not in a done stage.")
    stage_ids = fields.One2many('pos.prep.stage', 'prep_display_id', string="Stages", default=[
        {'name': 'To prepare', 'color': '#6C757D', 'alert_timer': 10},
        {'name': 'Ready', 'color': '#4D89D1', 'alert_timer': 5},
        {'name': 'Completed', 'color': '#4ea82a', 'alert_timer': 0}
    ])
    contains_bar_restaurant = fields.Boolean("Is a Bar/Restaurant", compute='_compute_contains_bar_restaurant', store=True)
    access_token = fields.Char("Access Token", default=lambda self: self._ensure_access_token())
    auto_clear = fields.Boolean(string='Auto clear', help='Time after which ready order will be removed from Order Status Screen.', default=False)
    clear_time_interval = fields.Integer(string='Interval auto clear time', default=10, help="Interval in minutes")

    @api.constrains('clear_time_interval')
    def _check_clear_time_interval_positive(self):
        for record in self:
            if record.clear_time_interval <= 0:
                raise ValidationError(_("The interval auto clear time must be positive."))

    def _load_preparation_data_models(self):
        return ['pos.category', 'pos.prep.order', 'pos.order', 'pos.prep.state', 'pos.prep.line', 'pos.prep.stage', 'product.product', 'pos.preset', 'product.attribute', 'product.template.attribute.value', 'resource.calendar.attendance', 'product.attribute.custom.value', 'pos.config']

    def load_preparation_data(self):
        # Init our first record, in case of self_order is pos_config
        pdis_fields = self._load_pos_preparation_data_fields()
        response = {
            'pos.prep.display': self.search_read([('id', '=', self.id)], pdis_fields, load=False),
        }
        for model in self._load_preparation_data_models():
            try:
                response[model] = self.env[model]._load_pos_preparation_data(response)
            except AccessError:
                response[model] = []

        return response

    def load_data_params(self):
        response = {}
        fields = self._load_pos_preparation_data_fields()
        response['pos.prep.display'] = {
            'fields': fields,
            'relations': self.env['pos.session']._load_pos_data_relations('pos.prep.display', fields)
        }

        for model in self._load_preparation_data_models():
            fields = self.env[model]._load_pos_preparation_data_fields()
            response[model] = {
                'fields': fields,
                'relations': self.env['pos.session']._load_pos_data_relations(model, fields)
            }

        return response

    def _get_pos_config_ids(self):
        self.ensure_one()
        if not self.pos_config_ids:
            return self.env['pos.config'].search([])
        else:
            return self.pos_config_ids

    @api.model
    def _get_preparation_displays(self, posOrder, pos_categ_ids):
        config_id = posOrder.config_id.id
        return self.env['pos.prep.display'].search([
            '&',
            '|', ('pos_config_ids', '=', False),
            ('pos_config_ids', 'in', config_id),
            '|', ('category_ids', 'in', pos_categ_ids),
            ('category_ids', '=', False)])

    def _get_open_orderlines_in_display(self):
        self.ensure_one()
        last_stage_id = self.stage_ids.ids[-1] if self.stage_ids.ids else 0
        pdis_orderlines = self.env['pos.prep.state'].search([
            ('stage_id', 'in', self.stage_ids.ids),
            '!', '&', ('todo', '=', False), ('stage_id', '=', last_stage_id)])
        pdis_orderlines = pdis_orderlines.filtered(lambda s: s.prep_line_id.prep_order_id.pos_order_id.session_id.state not in ['closed', 'closing_control'] or (s.prep_line_id.prep_order_id.pos_order_id.preset_time and s.prep_line_id.prep_order_id.pos_order_id.preset_time.date() > fields.Date.today()))
        return pdis_orderlines

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [
            (
                "id",
                "in",
                [
                    display.id
                    for display in self.env["pos.prep.display"]
                    .search([])
                    .filtered(
                        lambda d: not d.pos_config_ids
                        or config.id in d.pos_config_ids.ids
                    )
                ],
            )
        ]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ['id', 'category_ids', 'write_date']

    @api.depends('stage_ids', 'pos_config_ids', 'category_ids')
    def _compute_order_count(self):
        for preparation_display in self:
            open_pdis_lines = preparation_display._get_open_orderlines_in_display()
            progress_orders = open_pdis_lines.filtered(lambda sate: sate.stage_id.id != preparation_display.stage_ids[-1].id).prep_line_id.prep_order_id
            preparation_display.order_count = len(progress_orders)

            completed_order_times = []
            done_orders = self.env['pos.prep.order'].search([]) - open_pdis_lines.prep_line_id.prep_order_id
            for order in done_orders:
                order_lines = self.env['pos.prep.state'].search([('prep_line_id.prep_order_id', '=', order.id), ('stage_id.id', 'in', preparation_display.stage_ids.ids)])
                if order_lines:
                    completed_order_times.append((max(state.write_date for state in order_lines) - order.pos_order_id.create_date).total_seconds())

            preparation_display.average_time = round(sum(completed_order_times) / len(completed_order_times) / 60) if completed_order_times else 0

    # if needed the user can instantly reset a preparation display and archive all the orders.
    def reset(self):
        for preparation_display in self:
            preparation_display._get_open_orderlines_in_display().unlink()

            preparation_display._send_load_orders_message()

    def _send_load_orders_message(self, sound=False, notification=None, orderId=None):
        self.ensure_one()
        self._notify('LOAD_ORDERS', {'sound': sound, 'notification': notification, 'orderId': orderId})

    def open_ui(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/pos_preparation_display/web?display_id=%d' % self.id,
            'target': 'self',
        }

    def _send_notification(self, sound=False, notification=None):
        self.ensure_one()
        self._notify('NOTIFICATION', {'sound': sound, 'notification': notification})

    def open_reset_wizard(self):
        return {
            'name': _("Reset Preparation Display"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.preparation.display.reset.wizard',
            'target': 'new',
            'context': {'prep_display_id': self.id}
        }

    def _get_preparation_display_order_additional_info(self, prep_states, prep_lines, prep_orders):
        return {
            'pos.prep.state': prep_states.read(prep_states._load_pos_preparation_data_fields(), load=False),
            'pos.prep.order': prep_orders.read(prep_orders._load_pos_preparation_data_fields(), load=False),
            'pos.prep.line': prep_lines.read(prep_lines._load_pos_preparation_data_fields(), load=False),
            'pos.order': prep_orders.pos_order_id.read(prep_orders.pos_order_id._load_pos_preparation_data_fields(), load=False),
            'product.product': prep_lines.product_id.read(prep_lines.product_id._load_pos_preparation_data_fields(), load=False),
            'product.template.attribute.value': prep_lines.attribute_value_ids.read(prep_lines.attribute_value_ids._load_pos_preparation_data_fields(), load=False),
            'product.attribute': prep_lines.attribute_value_ids.attribute_id.read(prep_lines.attribute_value_ids.attribute_id._load_pos_preparation_data_fields(), load=False),
            'product.attribute.custom.value': prep_lines.pos_order_line_id.custom_attribute_value_ids.read(prep_lines.pos_order_line_id.custom_attribute_value_ids._load_pos_preparation_data_fields(), load=False),
        }

    def get_preparation_display_order(self, orderId):
        self.ensure_one()
        prep_states = self._get_open_orderlines_in_display()
        if orderId:
            prep_states = prep_states.filtered(lambda l: l.prep_line_id.prep_order_id.pos_order_id.id == orderId)
        prep_lines = prep_states.prep_line_id + self.env['pos.prep.line'].search([('combo_line_ids', 'in', prep_states.prep_line_id.ids)])
        return self._get_preparation_display_order_additional_info(prep_states, prep_lines, prep_lines.prep_order_id)

    @api.constrains('stage_ids')
    def _check_stage_ids(self):
        for preparation_display in self:
            if len(preparation_display.stage_ids) == 0:
                raise ValidationError(_("A preparation display must have a minimum of one step."))
            # If any session is open, the stages cannot be modified.
            linked_pos_configs = preparation_display._get_pos_config_ids()
            if any(linked_pos_configs.mapped('session_ids').filtered(lambda s: s.state == 'opened')):
                raise ValidationError(_("You cannot modify the stages of a preparation display that has an active sessions."))

    @api.depends('pos_config_ids')
    def _compute_contains_bar_restaurant(self):
        for preparation_display in self:
            preparation_display.contains_bar_restaurant = any(pos_config_id.module_pos_restaurant for pos_config_id in preparation_display._get_pos_config_ids())

    @api.model
    def pos_has_valid_product(self):
        return self.env['product.product'].sudo().search_count([('available_in_pos', '=', True), ('list_price', '>=', 0), ('id', 'not in', self.env['pos.config']._get_special_products().ids)], limit=1) > 0
