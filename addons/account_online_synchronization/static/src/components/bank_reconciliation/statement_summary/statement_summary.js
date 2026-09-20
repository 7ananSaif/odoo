import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { BankRecStatementSummary } from "@account_accountant/components/bank_reconciliation/statement_summary/statement_summary";

patch(BankRecStatementSummary, {
    props: {
        ...BankRecStatementSummary.props,
        journalAvailableBalanceAmount: { type: String, optional: true },
    },
});

patch(BankRecStatementSummary.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    },

    async actionOpenPendingBankStatementLines() {
        this.action.doActionButton({
            type: "object",
            resId: this.props.journalId,
            name: "action_open_pending_bank_statement_lines",
            resModel: "account.journal",
        });
    },
});
