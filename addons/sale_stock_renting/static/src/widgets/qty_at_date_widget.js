import {
    QtyAtDatePopover,
    QtyAtDateWidget,
    qtyAtDateWidget,
} from "@sale_stock/widgets/qty_at_date_widget";
import { formatDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(QtyAtDatePopover.prototype, {
    setup() {
        super.setup();
        this.orm = useService('orm');
    },

    async openRentalGanttView() {
        const action = await this.orm.call(
            'product.product', 'action_view_rentals', [this.props.record.data.product_id.id]
        );
        this.actionService.doAction(action);
    },
});

patch(QtyAtDateWidget.prototype, {
    updateCalcData() {
        const { data } = this.props.record;
        if (!data.product_id) {
            return;
        }
        if (!data.is_rental || !data.return_date || !data.start_date) {
            return super.updateCalcData();
        }
        this.calcData.stock_end_date = formatDateTime(data.return_date, { format: localization.dateFormat });
        this.calcData.stock_start_date = formatDateTime(data.start_date, { format: localization.dateFormat });
    },
});

export const rentalQtyAtDateWidget = {
    ...qtyAtDateWidget,
    fieldDependencies: [
        ...qtyAtDateWidget.fieldDependencies,
        { name: 'start_date', type: 'datetime' },
        { name: 'return_date', type: 'datetime' },
    ],
};
patch(qtyAtDateWidget, rentalQtyAtDateWidget);
