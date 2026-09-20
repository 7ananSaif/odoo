import { BankRecKanbanRenderer } from "@account_accountant/components/bank_reconciliation/kanban_renderer";
import { patch } from "@web/core/utils/patch";
import { onWillStart } from "@odoo/owl";

patch(BankRecKanbanRenderer.prototype, {
    setup() {
        super.setup();

        onWillStart(async () => {
            await this.bankReconciliation.updateHasAvailableBatchPayments(
                this.globalState.journalId
            );
        });
    },
});
