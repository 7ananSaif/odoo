import { patch } from "@web/core/utils/patch";
import { BankRecKanbanRenderer } from "@account_accountant/components/bank_reconciliation/kanban_renderer";

patch(BankRecKanbanRenderer.prototype, {
    async getJournalTotalAmount() {
        const values = await super.getJournalTotalAmount();
        this.globalState.journalAvailableBalanceAmount = values.available_balance_amount || "";
    },
});
