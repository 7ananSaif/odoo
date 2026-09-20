import { EventBus, reactive, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class BankReconciliationService {
    constructor(env, services) {
        this.env = env;
        this.setup(env, services);
    }

    setup(env, services) {
        this.bus = new EventBus();
        this.orm = services["orm"];

        this.chatterState = reactive({
            visible:
                JSON.parse(
                    browser.sessionStorage.getItem("isBankReconciliationWidgetChatterOpened")
                ) ?? false,
            statementLine: null,
        });
        this.reconcileCountPerPartnerId = reactive({});
        this.reconcileModelPerStatementLineId = reactive({});
    }

    toggleChatter() {
        this.chatterState.visible = !this.chatterState.visible;
        browser.sessionStorage.setItem(
            "isBankReconciliationWidgetChatterOpened",
            this.chatterState.visible
        );
    }

    /**
     * Specific function to open the chatter.
     * For a particular case, where the customer clicks on
     * the chatter icon directly on the bank statement line,
     * we want to open the chatter but not close it.
     */
    openChatter() {
        this.chatterState.visible = true;
    }

    selectStatementLine(statementLine) {
        this.chatterState.statementLine = statementLine;
    }

    reloadChatter() {
        this.bus.trigger("MAIL:RELOAD-THREAD", {
            model: "account.move",
            id: this.statementLineMoveId,
        });
    }

    async computeReconcileLineCountPerPartnerId(records) {
        const groups = await this.orm.formattedReadGroup(
            "account.move.line",
            [
                ["parent_state", "in", ["draft", "posted"]],
                [
                    "partner_id",
                    "in",
                    records
                        .filter((record) => !!record.data.partner_id.id)
                        .map((record) => record.data.partner_id.id),
                ],
                ["company_id", "child_of", records.map((record) => record.data.company_id.id)],
                ["search_account_id.reconcile", "=", true],
                ["display_type", "not in", ["line_section", "line_note"]],
                ["reconciled", "=", false],
                "|",
                ["search_account_id.account_type", "not in", ["asset_receivable", "liability_payable"]],
                ["payment_id", "=", false],
                ["statement_line_id", "not in", records.map((record) => record.data.id)],
            ],
            ["partner_id"],
            ["id:count"]
        );

        this.reconcileCountPerPartnerId = {};
        groups.forEach((group) => {
            this.reconcileCountPerPartnerId[group.partner_id[0]] = group["id:count"];
        });
    }

    async computeAvailableReconcileModels(records) {
        this.reconcileModelPerStatementLineId =
            Object.keys(records).length === 0
                ? {}
                : await this.orm.call(
                      "account.reconcile.model",
                      "get_available_reconcile_model_per_statement_line",
                      [records.map((record) => record.data.id)]
                  );
    }

    async updateAvailableReconcileModels(recordId) {
        const result = await this.orm.call(
            "account.reconcile.model",
            "get_available_reconcile_model_per_statement_line",
            [[recordId]]
        );
        this.reconcileModelPerStatementLineId[recordId] = result[recordId];
    }

    async reloadRecords(records) {
        await Promise.all([...records.map((record) => record.load())]);
    }

    get statementLineMove() {
        return this.chatterState.statementLine?.data.move_id;
    }

    get statementLineMoveId() {
        return this.statementLineMove?.id;
    }

    get statementLine() {
        return this.chatterState.statementLine;
    }

    get statementLineId() {
        return this.statementLine?.data?.id;
    }
}

const bankReconciliationService = {
    dependencies: ["orm"],
    start(env, services) {
        return new BankReconciliationService(env, services);
    },
};

registry.category("services").add("bankReconciliation", bankReconciliationService);

export function useBankReconciliation() {
    return useState(useService("bankReconciliation"));
}
