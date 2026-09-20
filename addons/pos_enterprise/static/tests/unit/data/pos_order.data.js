import { PosOrder } from "@point_of_sale/../tests/unit/data/pos_order.data";
import { patch } from "@web/core/utils/patch";

const { DateTime } = luxon;

patch(PosOrder.prototype, {
    sync_from_ui(data) {
        const records = super.sync_from_ui(data);
        if (!records["pos.order"].length || !odoo.preparation_display) {
            return records;
        }
        for (const order of records["pos.order"]) {
            const pdis_ticket = this.env["pos.prep.order"].create({
                pos_order_id: order.id,
                pdis_general_customer_note: order.general_customer_note || "",
                pdis_internal_note: order.internal_note || "[]",
                order_name: order.floating_order_name || order.tracking_number,
                write_date: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
            });
            const order_lines = this.env["pos.order.line"].browse(order.lines);
            for (let i = 0; i < order.lines.length; i++) {
                const line = order_lines[i];
                let parent_line = false;
                let parent = false;
                if (line.combo_parent_id) {
                    parent_line = order_lines.filter((l) => l.id == line.combo_parent_id);
                    parent = this.env["pos.prep.line"].search([
                        ["pos_order_line_uuid", "=", parent_line[0].uuid],
                        ["prep_order_id", "=", pdis_ticket],
                    ]);
                }
                const prep_line = this.env["pos.prep.line"].create({
                    internal_note: line.note || "[]",
                    attribute_value_ids: line.attribute_value_ids,
                    product_id: line.product_id,
                    quantity: line.qty,
                    prep_order_id: pdis_ticket,
                    pos_order_line_uuid: line.uuid,
                    pos_order_line_id: line.id,
                    combo_parent_id: parent?.[0] || false,
                    write_date: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
                });
                const combo_line_ids = order_lines.filter((l) => l.combo_parent_id === line.id);
                if (!combo_line_ids?.length) {
                    this.env["pos.prep.state"].create({
                        prep_line_id: prep_line,
                        stage_id: 1,
                        todo: true,
                        last_stage_change: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
                        write_date: DateTime.now().toFormat("yyyy-MM-dd HH:mm:ss"),
                    });
                }
            }
        }
        return records;
    },
});
