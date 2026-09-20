import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { onWillStart, onWillUpdateProps, useState, useEffect } from "@odoo/owl";

export class StockBarcodeQuantOne2ManyField extends X2ManyField {
    setup() {
        super.setup();
        this.state = useState({ selectedQuantId: null });
        this.moveLineData = this.props.record.data;
        this.quantRecords = this.moveLineData.product_stock_quant_ids.records;

        onWillStart(async () => {
            this.isQuantSelectable = false;
            const allowedOperationCodes = ["internal", "outgoing", "mrp_operation"];
            const validOperation = allowedOperationCodes.includes(this.moveLineData.picking_code);
            if (validOperation) {
                this.isQuantSelectable =
                    (await user.hasGroup("stock.group_production_lot")) ||
                    (await user.hasGroup("stock.group_stock_multi_locations")) ||
                    (await user.hasGroup("stock.group_tracking_lot")) ||
                    (await user.hasGroup("stock.group_tracking_owner"));
            }

            this._findMatchingQuant();
        });

        onWillUpdateProps(() => this._findMatchingQuant());

        useEffect(
            () => this._highlightSelectedQuant(),
            () => [this.state.selectedQuantId]
        );
    }

    async openRecord(record) {
        if (this.isQuantSelectable) {
            const vals = {
                location_id: record.data.location_id,
                lot_id: record.data.lot_id,
                package_id: record.data.package_id,
                owner_id: record.data.owner_id,
            };
            this.state.selectedQuantId = record.data.id;
            return await this.props.record.update(vals);
        }
        return;
    }

    /**
     * Finds the quant matching the current move line data.
     */
    _findMatchingQuant() {
        const matchedQuantRecord = this.quantRecords.find(({ data: quant }) => {
            const { location_id, lot_id, package_id, owner_id } = quant;
            return (
                location_id?.id === this.moveLineData.location_id?.id &&
                lot_id?.id === this.moveLineData.lot_id?.id &&
                package_id?.id === this.moveLineData.package_id?.id &&
                owner_id?.id === this.moveLineData.owner_id?.id
            );
        });
        this.state.selectedQuantId = matchedQuantRecord?.data.id || null;
    }

    _highlightSelectedQuant() {
        this.quantRecords.forEach((quant) => {
            quant.selected = quant.data.id === this.state.selectedQuantId;
        });
    }
}

export const stockBarcodeQuantOne2ManyField = {
    ...x2ManyField,
    component: StockBarcodeQuantOne2ManyField,
};

registry.category("fields").add("stock_barcode_quant_one2many", stockBarcodeQuantOne2ManyField);
