from odoo import api, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.constrains('refunded_orderline_id', 'price_subtotal')
    def _l10n_mx_edi_constrains_refunded_orderline_id(self):
        self.order_id._l10n_mx_edi_constrains_amount_total()

    def _l10n_mx_edi_cfdi_lines(self):
        """ Filter the order lines to be considered when creating the CFDI.

        :return: A recordset of order lines.
        """
        return self.filtered(lambda line: not line.order_id.currency_id.is_zero(line.price_unit * line.qty))

    def _prepare_base_line_for_taxes_computation(self):
        # EXTENDS 'point_of_sale'
        line = super()._prepare_base_line_for_taxes_computation()
        if (
            self.order_id.country_code == 'MX'
            and self.order_id.is_refund
            and self.company_id.l10n_mx_income_return_discount_account_id
        ):
            line['account_id'] = self.company_id.l10n_mx_income_return_discount_account_id
        elif (
            self.order_id.country_code == 'MX'
            and self.order_id.session_id.state == 'closed'
            and self.company_id.l10n_mx_income_re_invoicing_account_id
        ):
            line['account_id'] = self.company_id.l10n_mx_income_re_invoicing_account_id

        return line
