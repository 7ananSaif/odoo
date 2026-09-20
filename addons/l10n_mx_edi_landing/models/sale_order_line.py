from collections import defaultdict

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    l10n_mx_edi_can_use_customs_invoicing = fields.Boolean(
        compute='_compute_l10n_mx_edi_can_use_customs_invoicing',
        precompute=True,
        store=True
    )

    @api.depends('product_id')
    def _compute_l10n_mx_edi_can_use_customs_invoicing(self):
        for so_line in self:
            company = so_line.order_id.company_id or self.env.company
            so_line.l10n_mx_edi_can_use_customs_invoicing = so_line.product_id.with_company(company).l10n_mx_edi_can_use_customs_invoicing

    def _prepare_invoice_lines_vals_list(self, **optional_values):
        # OVERRIDE
        vals_list = super()._prepare_invoice_lines_vals_list(**optional_values)
        if self.company_id.country_code == 'MX' and self.l10n_mx_edi_can_use_customs_invoicing:
            new_vals_list = []
            qties_to_invoice = self._get_l10n_mx_edi_customs_qty_to_invoice()
            sign = 1 if self.qty_to_invoice < 0 else -1
            # Considering that there might be many invoice vals now for this sole line
            for vals in vals_list:
                if vals["display_type"] != 'product' or vals["is_downpayment"]:
                    continue
                invoiced_qty = vals["quantity"]
                for customs, qty in qties_to_invoice.items():
                    if self.product_uom_id.is_zero(invoiced_qty):
                        break
                    if self.product_uom_id.is_zero(qty) or not self.product_uom_id.compare(qty, 0) * sign <= 0:
                        continue
                    qty_to_invoice = min(invoiced_qty, qty, key=abs)
                    new_vals_list.append({
                        **vals,
                        "l10n_mx_edi_customs_number": customs,
                        "quantity": qty_to_invoice,
                    })
                    invoiced_qty -= qty_to_invoice
                    qties_to_invoice[customs] -= qty_to_invoice

            vals_list = new_vals_list
        return vals_list

    def _get_l10n_mx_edi_customs_qty_to_invoice(self):
        self.ensure_one()

        def _compute_qty(qty, from_unit, inverse):
            return from_unit._compute_quantity(
                qty * (-1 if inverse else 1), self.product_uom_id, rounding_method="HALF-UP"
            )

        qty_to_invoice_by_customs = defaultdict(float)
        outgoing_moves, incoming_moves = self._get_outgoing_incoming_moves()
        sml_by_customs = (outgoing_moves | incoming_moves).move_line_ids.filtered(
            lambda ml: ml.state == 'done' and ml.product_id.tracking != 'none'
        ).grouped(lambda ml: ml.lot_id.sudo().l10n_mx_edi_customs_number)

        for customs, move_lines in sml_by_customs.items():
            delivered_qty = sum(
                _compute_qty(ml.quantity, ml.product_uom_id, ml.location_usage == 'customer') for ml in move_lines
            )
            qty_to_invoice_by_customs[customs] = delivered_qty

        invl_by_customs = self._get_invoice_lines().filtered(
            lambda l: l.parent_state != 'cancel' or l.move_id.payment_state == 'invoicing_legacy'
        ).grouped("l10n_mx_edi_customs_number")

        for customs, lines in invl_by_customs.items():
            invoiced_qty = sum(
                _compute_qty(invl.quantity, invl.product_uom_id, invl.move_type == 'out_refund') for invl in lines
            )
            qty_to_invoice_by_customs[customs] -= invoiced_qty

        return qty_to_invoice_by_customs
