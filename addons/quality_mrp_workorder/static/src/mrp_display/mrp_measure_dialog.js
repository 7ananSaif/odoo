import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { FloatField } from "@web/views/fields/float/float_field";

export class MrpMeasureDialog extends ConfirmationDialog {
    static template = "quality_mrp_workorder.MrpMeasureDialog";
    static props = {
        ...ConfirmationDialog.props,
        record: Object,
    };
    static components = {
        ...ConfirmationDialog.components,
        FloatField,
    };

    _cancel() {
        this.props.record.discard();
        this.props.close();
    }

    _dismiss() {
        this.props.record.discard();
    }
}
