import { BankRecChatter } from "./chatter/chatter";
import { BankRecQuickCreate } from "./quick_create/quick_create";
import { BankRecKanbanController } from "./kanban_controller";
import { BankRecStatementLine } from "./statement_line/statement_line";
import { BankRecStatementSummary } from "./statement_summary/statement_summary";
import { browser } from "@web/core/browser/browser";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { useState, onWillStart, onWillDestroy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "./bank_reconciliation_service";

export class BankRecKanbanRenderer extends KanbanRenderer {
    static template = "account_accountant.BankRecKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        BankRecQuickCreate,
        BankRecStatementSummary,
        BankRecStatementLine,
        BankRecChatter,
    };

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.bankReconciliation = useBankReconciliation();
        this.globalState = useState({
            resModel: this.env.model.config.resModel,
            context: this.env.model.config.context,
            quickCreate: {
                isVisible: false,
                quickCreateView: this.props.archInfo.quickCreateView,
            },
            journalId:
                this.env.model.config.context.default_journal_id ||
                this.env.model.config.context.active_id,
            totalJournalAmount: "",
        });

        this.env.model.hooks.onRootLoaded = async (newRoot) => {
            await this.prepareInitialState(newRoot.records);
        }

        this.env.bus.addEventListener("createRecordQuickCreate", () => {
            this.globalState.quickCreate.isVisible = true;
        });

        onWillStart(async () => {
            await this.prepareInitialState(this.env.model.root.records);
        });

        onWillDestroy(() => {
            browser.sessionStorage.setItem(
                "isBankReconciliationWidgetChatterOpened",
                this.bankReconciliation.chatterState.visible
            );
            browser.sessionStorage.setItem(
                "bankReconciliationStatementLineId",
                this.bankReconciliation.chatterState.statementLine?.data.id
            );
            this.bankReconciliation.chatterState.statementLine = null;
        });
    }

    /**
     * Prepare the initial bank reconciliation widget info on load or when records changes
     *
     * @param {Array<Object>} records - Bank statement line records
     * @returns {Promise<void>} Resolves when all computations are done
     */
    async prepareInitialState(records){
        await Promise.all([
            this.getJournalTotalAmount(),
            this.bankReconciliation.computeReconcileLineCountPerPartnerId(records),
            this.bankReconciliation.computeAvailableReconcileModels(records),
        ]);
        const statementLineId =
            parseInt(browser.sessionStorage.getItem("bankReconciliationStatementLineId")) ||
            records[0]?.data.id;
        const statementLine =
            records.find((record) => record.data.id === statementLineId) ?? records[0];
        this.bankReconciliation.selectStatementLine(statementLine);
    }

    /**
        Override.
    **/
    cancelQuickCreate() {
        this.globalState.quickCreate.isVisible = false;
    }

    /**
        Override.
    **/
    async validateQuickCreate(recordId, mode) {
        // When adding a record, some information needs to be recomputed
        await this.bankReconciliation.updateAvailableReconcileModels(recordId);
        await this.env.model.load();
        await this.getJournalTotalAmount();
        await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
            this.env.model.root.records
        );

        if (mode === "add_close") {
            this.globalState.quickCreate.isVisible = false;
        }
    }

    async getJournalTotalAmount() {
        const value = await this.orm.call("account.journal", "get_total_journal_amount", [
            this.globalState.journalId,
        ]);
        this.globalState.totalJournalAmount = value.balance_amount;
        this.globalState.totalIsInvalid = value.has_invalid_statements;
        return value;
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------
    async actionOpenBankGL() {
        const actionData = await this.orm.call(
            "account.journal",
            "action_open_bank_balance_in_gl",
            [
                this.env.model.config.context.default_journal_id ||
                    this.env.model.config.context.active_id,
            ],
        );
        this.action.doAction(actionData);
    }

    actionOpenStatement(statementId) {
        const action = {
            type: "ir.actions.act_window",
            res_model: "account.bank.statement",
            res_id: statementId,
            views: [[false, "form"]],
            target: "current",
            context: {
                form_view_ref: "account_accountant.view_bank_statement_form_bank_rec_widget",
            },
        };

        this.action.doAction(action);
    }

    // -----------------------------------------------------------------------------
    // GETTER
    // -----------------------------------------------------------------------------

    get quickCreateContext() {
        return {
            ...this.globalState.context,
        };
    }

    // TODO: remove in master
    get hideCurrentBalance() {
        return false;
    }

    get hasStatementLine() {
        return this.env.model.root.count;
    }

    get totalJournalLabel() {
        return _t("Current Balance");
    }

    /**
    Prepares a list of statements based on the statement_id of the bank statement line records.
    Statements are only displayed above the first line of the statement (all lines might not be visible in the kanban)
    **/
    get statementGroups() {
        const statementGroups = {};
        let lastStatementId = null;
        for (const record of this.env.model.root.records) {
            const statementId = record.data.statement_id?.id;
            if (statementId && statementId !== lastStatementId) {
                // Add the statement group information to the statementGroups object
                statementGroups[record.data.id] = {
                    statementId: statementId,
                    name: record.data.statement_name,
                    balance: formatMonetary(record.data.statement_balance_end_real, {
                        currencyId: record.data.currency_id.id,
                    }),
                    isValid: record.data.statement_complete && record.data.statement_valid,
                };
                lastStatementId = statementId;
            } else {
                if (
                    Object.keys(statementGroups).length &&
                    !statementId &&
                    typeof lastStatementId !== "string"
                ) {
                    statementGroups[record.data.id] = {
                        name: _t("No Bank Statement"),
                        isValid: true,
                    };
                    lastStatementId = "no_bank_statement";
                }
            }
        }
        return statementGroups;
    }

    get isQuickCreateVisible() {
        return this.globalState.quickCreate.isVisible;
    }
}

export const BankRecKanbanView = {
    ...kanbanView,
    Controller: BankRecKanbanController,
    Renderer: BankRecKanbanRenderer,
    searchMenuTypes: ["filter", "favorite"],
};

registry.category("views").add("bank_rec_widget_kanban", BankRecKanbanView);
