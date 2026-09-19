import { BankRecButtonList } from "../button_list/button_list";
import { BankRecLineToReconcile } from "../line_to_reconcile/line_to_reconcile";
import { BankRecReconciledLineName } from "../reconciled_line_name/reconciled_line_name";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatMonetary } from "@web/views/fields/formatters";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState, useRef } from "@odoo/owl";
import { useBankReconciliation } from "../bank_reconciliation_service";

export class BankRecStatementLine extends KanbanRecord {
    static template = "account_accountant.BankRecStatementLine";
    static components = {
        BankRecLineToReconcile,
        BankRecButtonList,
        DropdownItem,
        BankRecReconciledLineName,
    };
    static props = [...KanbanRecord.props];

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.bankReconciliation = useBankReconciliation();
        this.state = useState({
            isUnfolded: false,
        });
        this.statementLineRootRef = useRef("root");
        if (this.env.model.config.context?.default_st_line_id === this.props.record.resId) {
            this.state.isUnfolded = true;
            this.bankReconciliation.selectStatementLine(this.props.record);
        }
        onWillStart(async () => {
            this.userCanReview = await user.hasGroup("account.group_account_user");
        });
    }

    getRecordClasses() {
        let classes = super.getRecordClasses();
        if (this.hasStatementLine === 1) {
            classes += " mt-3";
        }
        return classes;
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------

    openStatementCreate() {
        this.action.doAction("account_accountant.action_bank_statement_form_bank_rec_widget", {
            additionalContext: {
                split_line_id: this.recordData.id,
                default_journal_id: this.recordData.journal_id.id,
            },
            onClose: async () => {
                this.env.model.load();
            },
        });
    }

    openPartner() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.partner.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async removePartner() {
        await this.orm.write("account.bank.statement.line", [this.recordData.id], {
            partner_id: false,
        });
        this.record.load();
    }

    // -----------------------------------------------------------------------------
    // HELPER
    // -----------------------------------------------------------------------------
    get reconciledLineName() {
        const reconciledLine = {};
        for (const line of this.linesToReconcile) {
            if (
                line.reconciled_lines_excluding_exchange_diff_ids.records.length === 1 &&
                line.reconciled_lines_excluding_exchange_diff_ids.records[0].data.move_name
            ) {
                reconciledLine[line.id] = {
                    move: line.reconciled_lines_excluding_exchange_diff_ids.records[0].data
                        .move_name,
                };
            } else if (line.tax_ids.count) {
                reconciledLine[line.id] = { tax: line.tax_ids.records };
            } else {
                reconciledLine[line.id] = { account: line.account_id.display_name };
            }
        }
        return reconciledLine;
    }

    get record() {
        return this.props.record;
    }

    get recordData() {
        return this.props.record.data;
    }

    fold() {
        if (this.state.isUnfolded) {
            this.toggleUnfold();
        }
        this.selectStatementLine();
    }

    unfold() {
        if (!this.state.isUnfolded) {
            this.toggleUnfold();
        }
        this.selectStatementLine();
    }

    toggleUnfold() {
        this.state.isUnfolded = !this.isUnfolded;
        this.selectStatementLine();
    }

    selectStatementLine() {
        // Update the chatter with the last selected element
        this.bankReconciliation.selectStatementLine(this.record);
    }

    openChatter() {
        this.selectStatementLine();
        this.bankReconciliation.openChatter();
    }

    get hasInvalidAnalytics() {
        return this.linesToReconcile.some((line) => line.has_invalid_analytics);
    }

    get isUnfolded() {
        return this.state.isUnfolded;
    }

    get hasStatementLine() {
        return this.env.model.root.count;
    }

    get formattedAmount() {
        return formatMonetary(this.recordData.amount, {
            currencyId: this.recordData.currency_id.id,
        });
    }

    get formattedDate() {
        return this.recordData.date.toLocaleString({
            month: "short",
            day: "2-digit",
        });
    }

    get formattedFullDate() {
        return this.recordData.date.toLocaleString({
            month: "long",
            day: "numeric",
            year: "numeric",
        });
    }

    get partner() {
        return this.recordData.partner_id;
    }

    get linesToReconcile() {
        return this.accountMoveLines.filter((line) => {
            return (
                line.account_id.id !== this.recordData.journal_id?.suspense_account_id.id &&
                line.account_id.id !== this.recordData.journal_id?.default_account_id.id
            );
        });
    }

    get suspenseAccountLine() {
        return this.accountMoveLines.filter((line) => {
            return line.account_id.id === this.recordData.journal_id.suspense_account_id.id;
        })?.[0];
    }

    get accountMoveLines() {
        return [...this.recordData.line_ids.records.map((line) => line.data)];
    }

    get hasForeignCurrencyAndSameCurrencyForAllLines() {
        return (
            this.recordData.foreign_currency_id &&
            this.linesToReconcile &&
            this.linesToReconcile.filter((line) => {
                return line.currency_id.id !== this.recordData.foreign_currency_id.id;
            }).length === 0
        );
    }

    get suspenseAccountLineFormattedAmount() {
        return formatMonetary(this.suspenseAccountLine.amount_currency, {
            currencyId: this.suspenseAccountLine?.currency_id.id,
        });
    }

    get activityNumber() {
        return this.recordData.activity_ids.count;
    }

    /**
     * Checks if there is at least one attachment associated with the bank statement line or its related records.
     *
     * This getter aggregates attachment counts from:
     * - The bank statement line record itself or the related move since attachment_ids is a related to move_id.attachment_ids.
     * - The related move lines themselves, if they have attachments directly associated (`line.move_attachment_ids`)
     *   except the attachments link to the statement.
     * - The lines reconciled with the related move lines, specifically checking for attachments on the
     *   move associated with those reconciled lines.
     *
     * This check ensures that all attachments from associated invoices, bills, and other related documents are considered.
     *
     * @returns {number} The total number of attachments found. A return value greater than 0 indicates the presence of attachments.
     */
    get hasAttachment() {
        const statementAttachment = this.recordData.bank_statement_attachment_ids.records.map(
            (attachment) => attachment.data.id
        );

        return (
            this.recordData.attachment_ids.records.length +
            this.linesToReconcile
                .flatMap((line) => line.reconciled_lines_ids.records)
                .filter((line) => line.data.move_attachment_ids?.count)
                .reduce(
                    (accumulator, line) =>
                        parseInt(accumulator) + parseInt(line.data.move_attachment_ids.count),
                    0
                ) +
            this.linesToReconcile
                .filter(
                    (line) =>
                        line.move_attachment_ids?.count &&
                        !line.move_attachment_ids.records
                            .map((attachment) => attachment.data.id)
                            .every((id) => statementAttachment.includes(id))
                )
                .reduce(
                    (accumulator, line) =>
                        parseInt(accumulator) + parseInt(line.move_attachment_ids.count),
                    0
                )
        );
    }

    get amountClasses() {
        const classes = this.recordData.foreign_currency_id ? "w-50" : "w-100";
        if (this.recordData.amount > 0) {
            return `${classes} fw-bold`;
        }
        if (this.recordData.amount < 0) {
            return `${classes} text-danger fw-bold`;
        }
        return `${classes} text-secondary`;
    }

    get buttonListProps() {
        return {
            statementLineRootRef: this.statementLineRootRef,
            statementLine: this.record,
            reconcileLineCount:
                this.bankReconciliation.reconcileCountPerPartnerId[this.recordData.partner_id.id] ??
                null,
            reconcileModels:
                this.bankReconciliation.reconcileModelPerStatementLineId[this.recordData.id] ?? [],
            preSelectedReconciliationModel: this.accountMoveLines
                .filter((line) => line.reconcile_model_id.id)
                .map((line) => line.reconcile_model_id)?.[0],
        };
    }

    get formattedAmountCurrencyInForeign() {
        return formatMonetary(this.recordData.amount_currency, {
            currencyId: this.recordData.foreign_currency_id.id,
        });
    }

    get isSelected() {
        return this.recordData.move_id.id === this.bankReconciliation.statementLineMoveId;
    }

    get isChatterOpen() {
        return this.bankReconciliation.chatterState.visible;
    }
}
