import { patch } from "@web/core/utils/patch";

import { SMLX2ManyField } from "@stock/fields/stock_move_line_x2_many_field";

patch(SMLX2ManyField.prototype, {
    get _move_line_ids() {
        if (this.props.record.data.move_line_ids_picked) {
            return this.props.record.data.move_line_ids_picked.records;
        }
        return super._move_line_ids;
    },
});
