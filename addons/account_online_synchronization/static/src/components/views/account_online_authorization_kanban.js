import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban_controller";

patch(BankRecKanbanController.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
        this.displayDuplicateWarning = !!this.props.context.duplicates_from_date;
    },

    async onWarningClick() {
        const { context } = this.env.searchModel;
        return this.action.doActionButton({
            type: "object",
            resModel: "account.journal",
            name: "action_open_duplicate_transaction_wizard",
            resId: context.default_journal_id || context.active_id,
            args: JSON.stringify([context.duplicates_from_date]),
        });
    },
});
