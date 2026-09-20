from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_new_picking_values(self):
        values = super()._get_new_picking_values()
        order = self.sale_line_id.order_id
        if not order.client_order_ref or order.company_id.account_fiscal_country_id.code != 'CL' or not order.company_id.l10n_cl_dte_service_provider:
            return values

        purchase_order_doc_type_id = self.env.ref('l10n_cl.dc_odc')
        if original_reference_ids := self.move_orig_ids.picking_id.l10n_cl_reference_ids.filtered(lambda ref: ref.l10n_cl_reference_doc_type_id == purchase_order_doc_type_id):
            # We copy the purchase order reference from a previous picking to the next to make sure
            # that if the customer changed the reference in the pick stage, it doesn't get overriden
            # with the hardcoded default data from the sale order.
            reference_data = [
                [4, reference.copy().id, 0]
                for reference in original_reference_ids
            ]
        else:
            reference_data = [[0, 0, {
                'origin_doc_number': order.client_order_ref,
                'l10n_cl_reference_doc_type_id': purchase_order_doc_type_id.id,
                'reason': self.env._("Cross Reference To Purchase Order"),
                'date': order.date_order,
            }]]

        values['l10n_cl_reference_ids'] = reference_data
        return values
