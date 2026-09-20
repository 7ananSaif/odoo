import { AddressRecurrencyConfirmationDialog } from "@planning/components/address_recurrency_confirmation_dialog/address_recurrency_confirmation_dialog";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";
import { usePlanningRecurringDeleteAction } from "../planning_hooks";

export class PlanningKanbanController extends KanbanController {
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

    async deleteRecord(record) {
        if (record.data.repeat) {
            this.dialogService.add(AddressRecurrencyConfirmationDialog, {
                confirm: async () => {
                    await this.planningRecurrenceDeletion._actionAddressRecurrency(
                        record,
                        this.state.recurrenceUpdate
                    );
                    this.model.root.deleteRecords([record])
                },
                onChangeRecurrenceUpdate: this.planningRecurrenceDeletion._setRecurrenceUpdate.bind(this),
                selected: this.state.recurrenceUpdate,
            });
        } else {
            super.deleteRecord(record);
        }
    }
}
