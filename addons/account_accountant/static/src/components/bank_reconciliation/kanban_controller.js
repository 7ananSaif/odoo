import { useSubEnv, onWillRender, onWillDestroy } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { makeActiveField } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "./bank_reconciliation_service";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { user } from "@web/core/user";

export class BankRecKanbanController extends KanbanController {
    static template = "account_accountant.BankRecoKanbanController";

    async setup() {
        super.setup();
        this.orm = useService("orm");
        this.bankReconciliation = useBankReconciliation();
        useSubEnv({
            bus: this.bankReconciliation.bus,
        });
        useHotkey("alt+shift+c", () => this.bankReconciliation.toggleChatter(), {
            bypassEditableProtection: true,
            withOverlay: () => this.rootRef.el.querySelector(".bank-chatter-btn"),
        });
        onWillRender(() => { user.updateContext({ from_bank_reco : true }) });
        onWillDestroy(() => { user.updateContext({ from_bank_reco : false }) });
    }

    async createRecord() {
        this.env.bus.trigger("createRecordQuickCreate");
    }

    getCheckedField() {
        return {
            fields: {
                checked: { name: "checked", type: "char", }
            },
            activeFields : {
                checked: makeActiveField(),
            }
        }
    }

    get modelParams() {
        const params = super.modelParams;
        params.config.activeFields.move_id = makeActiveField();
        params.config.activeFields.move_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                attachment_ids: { name: "attachment_ids", type: "one2many" },
                checked: { name: "checked", type: "char" },
            },
            activeFields: {
                attachment_ids: makeActiveField(),
                checked: makeActiveField(),
            },
        };
        params.config.activeFields.bank_statement_attachment_ids = makeActiveField();
        params.config.activeFields.bank_statement_attachment_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
            },
        };
        params.config.activeFields.attachment_ids = makeActiveField();
        params.config.activeFields.partner_id = makeActiveField();
        params.config.activeFields.partner_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                property_account_receivable_id: {
                    name: "property_account_receivable_id",
                    type: "many2one",
                },
                property_account_payable_id: {
                    name: "property_account_payable_id",
                    type: "many2one",
                },
                customer_rank: { name: "customer_rank", type: "int" },
                supplier_rank: { name: "supplier_rank", type: "int" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                property_account_receivable_id: makeActiveField(),
                property_account_payable_id: makeActiveField(),
                customer_rank: makeActiveField(),
                supplier_rank: makeActiveField(),
            },
        };

        params.config.activeFields.line_ids = makeActiveField();
        params.config.activeFields.line_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                name: { name: "name", type: "char" },
                balance: { name: "balance", type: "monetary" },
                amount_currency: { name: "amount_currency", type: "monetary" },
                currency_id: { name: "currency_id", type: "many2one" },
                currency_rate: { name: "currency_rate", type: "float" },
                is_same_currency: { name: "is_same_currency", type: "boolean" },
                company_currency_id: { name: "company_currency_id", type: "many2one" },
                account_id: { name: "account_id", type: "many2one" },
                partner_id: { name: "partner_id", type: "many2one" },
                move_id: { name: "move_id", type: "many2one" },
                move_attachment_ids: { name: "move_attachment_ids", type: "one2many" },
                reconciled_lines_ids: { name: "reconciled_lines_ids", type: "many2many" },
                reconciled_lines_excluding_exchange_diff_ids: {
                    name: "reconciled_lines_excluding_exchange_diff_ids",
                    type: "many2many",
                },
                matched_debit_ids: { name: "matched_debit_ids", type: "one2many" },
                matched_credit_ids: { name: "matched_credit_ids", type: "one2many" },
                reconcile_model_id: { name: "reconcile_model_id", type: "many2one" },
                has_invalid_analytics: { name: "has_invalid_analytics", type: "boolean" },
                tax_line_id: { name: "tax_line_id", type: "many2one" },
                tax_ids: { name: "tax_ids", type: "many2many" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                name: makeActiveField(),
                balance: makeActiveField(),
                amount_currency: makeActiveField(),
                currency_id: makeActiveField(),
                currency_rate: makeActiveField(),
                is_same_currency: makeActiveField(),
                company_currency_id: makeActiveField(),
                account_id: makeActiveField(),
                partner_id: makeActiveField(),
                move_id: makeActiveField(),
                move_attachment_ids: makeActiveField(),
                reconciled_lines_ids: makeActiveField(),
                reconciled_lines_excluding_exchange_diff_ids: makeActiveField(),
                matched_debit_ids: makeActiveField(),
                matched_credit_ids: makeActiveField(),
                reconcile_model_id: makeActiveField(),
                has_invalid_analytics: makeActiveField(),
                tax_line_id: makeActiveField(),
                tax_ids: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.move_attachment_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.matched_debit_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                exchange_move_id: { name: "exchange_move_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                exchange_move_id: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.matched_debit_ids.related.activeFields.exchange_move_id.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    display_name: { name: "display_name", type: "char" },
                    line_ids: { name: "line_ids", type: "one2many" },
                },
                activeFields: {
                    id: makeActiveField(),
                    display_name: makeActiveField(),
                    line_ids: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.matched_debit_ids.related.activeFields.exchange_move_id.related.activeFields.line_ids.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    display_name: { name: "display_name", type: "char" },
                    balance: { name: "balance", type: "monetary" },
                },
                activeFields: {
                    id: makeActiveField(),
                    display_name: makeActiveField(),
                    balance: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.matched_credit_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                exchange_move_id: { name: "exchange_move_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                exchange_move_id: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.matched_credit_ids.related.activeFields.exchange_move_id.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    display_name: { name: "display_name", type: "char" },
                    line_ids: { name: "line_ids", type: "one2many" },
                },
                activeFields: {
                    id: makeActiveField(),
                    display_name: makeActiveField(),
                    line_ids: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.matched_credit_ids.related.activeFields.exchange_move_id.related.activeFields.line_ids.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    display_name: { name: "display_name", type: "char" },
                    balance: { name: "balance", type: "monetary" },
                },
                activeFields: {
                    id: makeActiveField(),
                    display_name: makeActiveField(),
                    balance: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.reconciled_lines_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                move_name: { name: "move_name", type: "char" },
                move_id: { name: "move_id", type: "many2one" },
                amount_currency: { name: "amount_currency", type: "monetary" },
                full_reconcile_id: { name: "full_reconcile_id", type: "many2one" },
                currency_id: { name: "currency_id", type: "many2one" },
                move_attachment_ids: { name: "move_attachment_ids", type: "one2many" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                move_name: makeActiveField(),
                move_id: makeActiveField(),
                amount_currency: makeActiveField(),
                full_reconcile_id: makeActiveField(),
                currency_id: makeActiveField(),
                move_attachment_ids: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.reconciled_lines_excluding_exchange_diff_ids.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    move_name: { name: "move_name", type: "char" },
                    move_id: { name: "move_id", type: "many2one" },
                },
                activeFields: {
                    id: makeActiveField(),
                    move_name: makeActiveField(),
                    move_id: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.reconciled_lines_ids.related.activeFields.move_id.related =
            this.getCheckedField();
        params.config.activeFields.line_ids.related.activeFields.reconciled_lines_excluding_exchange_diff_ids.related.activeFields.move_id.related =
            this.getCheckedField();
        params.config.activeFields.line_ids.related.activeFields.move_id.related =
            this.getCheckedField();
        params.config.activeFields.line_ids.related.activeFields.tax_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.partner_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                property_account_receivable_id: {
                    name: "property_account_receivable_id",
                    type: "many2one",
                },
                property_account_payable_id: {
                    name: "property_account_payable_id",
                    type: "many2one",
                },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                property_account_receivable_id: makeActiveField(),
                property_account_payable_id: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.account_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                account_type: { name: "account_type", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                account_type: makeActiveField(),
            },
        };
        params.config.activeFields.journal_id = makeActiveField();
        params.config.activeFields.journal_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                suspense_account_id: { name: "suspense_account_id", type: "many2one" },
                default_account_id: { name: "default_account_id", type: "many2one" },
                currency_id: { name: "currency_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                suspense_account_id: makeActiveField(),
                default_account_id: makeActiveField(),
                currency_id: makeActiveField(),
            },
        };
        params.config.activeFields.company_id = makeActiveField();
        params.config.activeFields.company_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                currency_id: { name: "currency_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                currency_id: makeActiveField(),
            },
        };
        return params;
    }
}
