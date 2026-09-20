import { BankRecButtonList } from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    selectBatchPayment() {
        this.addDialog(SelectCreateDialog, {
            title: _t("Search: Batch Payment"),
            noCreate: true,
            multiSelect: false,
            resModel: "account.batch.payment",
            context: { search_default_journal_id: this.statementLineData.journal_id.id },
            domain: [["state", "!=", "reconciled"]],
            onSelected: async (batch) => {
                await this.onSelectBatchPayment(batch[0]);
            },
        });
    },

    async onSelectBatchPayment(batchPaymentId) {
        await this.orm.call(
            "account.bank.statement.line",
            "set_batch_payment_bank_statement_line",
            [this.statementLineData.id, batchPaymentId]
        );
        await this.bankReconciliation.updateHasAvailableBatchPayments(
            this.statementLineData.journal_id.id
        );
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    },

    get buttons() {
        const buttonsToDisplay = super.buttons;
        if (this.isBatchPaymentsButtonShown) {
            buttonsToDisplay.batch = {
                label: _t("Batches"),
                action: this.selectBatchPayment.bind(this),
                classes: "batches-btn",
            };
        }
        return buttonsToDisplay;
    },

    get isBatchPaymentsButtonShown() {
        return this.bankReconciliation.hasAvailableBatchPayments.value;
    },
});
