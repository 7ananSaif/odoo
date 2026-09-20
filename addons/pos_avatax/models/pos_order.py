from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'account.external.tax.mixin', 'account.avatax.unique.code']

    def _get_and_set_external_taxes_on_eligible_records(self):
        """ account.external.tax.mixin override. """
        eligible_orders = self.filtered(lambda order: order.is_tax_computed_externally and order.state in ('draft'))
        eligible_orders._set_external_taxes(eligible_orders._get_external_taxes())
        return super()._get_and_set_external_taxes_on_eligible_records()

    def _get_line_data_for_external_taxes(self):
        """ account.external.tax.mixin override. """
        res = []
        for line in self.lines:
            # Clear all taxes (e.g. default customer tax). Not every line will be sent to the external tax
            # calculation service, those lines would keep their default taxes otherwise.
            line.tax_ids = False
            pos_config = line.order_id.config_id
            res.append({
                "id": line.id,
                "model_name": line._name,
                "product_id": line.product_id,
                "description": None,  # no line description on pos.order.line
                "qty": line.qty,
                "uom_id": line.product_uom_id,
                "price_subtotal": line.price_subtotal,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "is_refund": False,
                "warehouse_id": pos_config.warehouse_id if pos_config.ship_later else False
            })
        return res

    def _get_avatax_ship_to_partner(self):
        """ account.external.tax.mixin override. """
        return self.partner_id

    def _get_invoice_grouping_keys(self):
        res = super()._get_invoice_grouping_keys()
        if self.filtered('fiscal_position_id.is_avatax'):
            res += ['partner_id']
        return res

    def _get_avatax_address_from_partner(self, partner):
        if partner:
            return super()._get_avatax_address_from_partner(partner)
        raise ValidationError(_('Avatax requires your current location or a customer to be set on the order with a proper zip, state and country.'))

    @api.model
    def get_order_tax_details(self, orders):
        res = self.env['pos.order'].sync_from_ui(orders)
        order_ids = self.browse([order['id'] for order in res['pos.order']])
        results = {
            'pos.order': [],
            'pos.order.line': [],
            'account.tax': [],
            'account.tax.group': [],
        }

        for order in order_ids:
            order.button_external_tax_calculation()
            config = order.config_id
            results['account.tax'] += self.env['account.tax']._load_pos_data_read(order.lines.tax_ids, config)
            results['account.tax.group'] += self.env['account.tax.group']._load_pos_data_read(order.lines.tax_ids.tax_group_id, config)
            results['pos.order'] += self.env['pos.order']._load_pos_data_read(order, config)
            results['pos.order.line'] += self.env['pos.order.line']._load_pos_data_read(order.lines, config) if config else []

        return results
