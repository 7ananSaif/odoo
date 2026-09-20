import { BankReconciliationService } from "@account_accountant/components/bank_reconciliation/bank_reconciliation_service";
import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";

patch(BankReconciliationService.prototype, {
    setup(env, services) {
        super.setup(env, services);
        this.hasAvailableBatchPayments = reactive({ value: false });
    },

    async updateHasAvailableBatchPayments(journalId) {
        this.hasAvailableBatchPayments.value = !!(await this.orm.searchCount(
            "account.batch.payment",
            [
                ["state", "!=", "reconciled"],
                ["journal_id", "=", journalId],
            ],
            {
                limit: 1,
            }
        ));
    },
});
