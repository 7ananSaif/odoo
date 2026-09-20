from odoo import models
from odoo.addons.pos_enterprise.utils.date_utils import compute_seconds_since


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    def _get_pos_orders(self):
        self.ensure_one()
        if len(self.stage_ids) <= 1:
            return {"done": [], "notDone": []}
        last_stage = self.stage_ids[-1]  # last stage always means that the order is done.
        second_last_stage = self.stage_ids[-2]  # order will be displated as ready.

        orders_completed = set()
        orders_not_completed = set()
        orders_completed_ready_date = {}
        pdis_line_ids = self._get_open_orderlines_in_display().filtered(lambda o: o.stage_id != last_stage)

        for pdis_line_id in pdis_line_ids:
            order_stage_id = pdis_line_id.stage_id
            pos_order_tracking_ref = pdis_line_id.prep_line_id.prep_order_id.pos_order_id.tracking_number
            unfinished_pdis_orders = (
                (
                    line.prep_line_id.prep_order_id.pos_order_id == pdis_line_id.prep_line_id.prep_order_id.pos_order_id
                    and line.stage_id != second_last_stage
                    and pdis_line_id != line
                )
                for line in pdis_line_ids
            )
            if order_stage_id == second_last_stage and not any(unfinished_pdis_orders):
                order_ready_date = pdis_line_id.last_stage_change
                order_ready_delay = int(compute_seconds_since(order_ready_date) / 60)
                is_order_visible = not self.auto_clear or order_ready_delay < self.clear_time_interval
                if is_order_visible:
                    orders_completed.add(pos_order_tracking_ref)
                    orders_completed_ready_date[pos_order_tracking_ref] = str(order_ready_date)
            elif order_stage_id != last_stage:
                orders_not_completed.add(pos_order_tracking_ref)
        return {
            "done": list(orders_completed),
            "notDone": list(orders_not_completed),
            "ordersCompletedReadyDate": orders_completed_ready_date,
        }

    def _send_orders_to_customer_display(self):
        self.ensure_one()
        orders = self._get_pos_orders()
        self._notify("NEW_ORDERS", orders)

    def _send_load_orders_message(self, sound=False, notification=None, orderId=None):
        super()._send_load_orders_message(sound, notification, orderId)
        self._send_orders_to_customer_display()

    def open_customer_display(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/pos-order-tracking?access_token={self.access_token}",
            "target": "new",
        }
