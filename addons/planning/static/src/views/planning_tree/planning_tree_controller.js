import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { useState } from "@odoo/owl";
import { AddressRecurrencyConfirmationDialog } from "@planning/components/address_recurrency_confirmation_dialog/address_recurrency_confirmation_dialog";
import { usePlanningRecurringDeleteAction } from "../planning_hooks";

export class PlanningTreeController extends ListController {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
        this.state = useState({
            recurrenceUpdate: "this",
        });
        this.planningRecurrenceDeletion = usePlanningRecurringDeleteAction();
    }

    get modelOptions() {
        return {
            ...super.modelOptions,
            lazy: false,
        };
    }

    async onDeleteSelectedRecords() {
        const selectedRecords = this.model.root.selection;
        const recordsWithRecurrency_id = selectedRecords.filter((record) => record.data.recurrency_id);
        if (recordsWithRecurrency_id.length > 0) {
            this.dialogService.add(AddressRecurrencyConfirmationDialog, {
                confirm: async () => {
                    await this.planningRecurrenceDeletion._actionAddressRecurrency(
                        { resId: recordsWithRecurrency_id.map((record) => record.resId), resModel: this.props.resModel },
                        this.state.recurrenceUpdate
                    );
                    this.model.root.deleteRecords();
                },
                onChangeRecurrenceUpdate: this.planningRecurrenceDeletion._setRecurrenceUpdate.bind(this),
                selected: this.state.recurrenceUpdate,
            });
        } else {
            await super.onDeleteSelectedRecords();
        }
    }
}
