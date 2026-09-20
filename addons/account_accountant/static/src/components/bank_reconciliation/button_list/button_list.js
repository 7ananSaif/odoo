import { BankRecButton } from "../button/button";
import { BankRecFileUploader } from "../file_uploader/file_uploader";
import { Component } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { BankRecSelectCreateDialog } from "../search_dialog/search_dialog";
import { _t } from "@web/core/l10n/translation";
import { getCurrency } from "@web/core/currency";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

export class BankRecButtonList extends Component {
    static template = "account_accountant.BankRecButtonList";
    static components = {
        Dropdown,
        DropdownItem,
        BankRecButton,
        BankRecFileUploader,
    };
    static props = {
        statementLineRootRef: { type: Object },
        statementLine: { type: Object },
        suspenseAccountLine: { type: Object, optional: true },
        reconcileLineCount: { type: [Number, { value: null }], optional: true },
        reconcileModels: Array,
        preSelectedReconciliationModel: { type: Object, optional: true },
    };
    static defaultProps = {
        reconcileLineCount: 0,
    };

    setup() {
        this.action = useService("action");
        this.ui = useService("ui");
        this.orm = useService("orm");

        this.addDialog = useOwnedDialogs();
        this.currencyDigits = getCurrency(this.statementLineData.currency_id.id)?.digits || 2;
        this.bankReconciliation = useBankReconciliation();

        this.registerHotkeys();
    }

    restoreFocus() {
        if (this.isLineSelected) {
            this.props.statementLineRootRef.el.focus();
        }
    }

    /**
     * Displays a search dialog (no create option) for selecting a `res.partner` record.
     */
    setPartnerOnReconcileLine() {
        this.addDialog(
            SelectCreateDialog,
            {
                title: _t("Search: Partner"),
                noCreate: false,
                multiSelect: false,
                resModel: "res.partner",
                context: { default_name: this.statementLineData.partner_name },
                onSelected: async (partner) => {
                    await this.orm.call(
                        "account.bank.statement.line",
                        "set_partner_bank_statement_line",
                        [this.statementLineData.id, partner[0]]
                    );
                    const recordsToLoad = [];
                    if (this.statementLineData.partner_name) {
                        // Reload all impacted statement lines if we have a partner_name
                        recordsToLoad.push(
                            ...this.env.model.root.records.filter(
                                (record) =>
                                    record.data.partner_name === this.statementLineData.partner_name
                            )
                        );
                    } else {
                        recordsToLoad.push(this.props.statementLine);
                    }
                    await this.bankReconciliation.reloadRecords(recordsToLoad);
                    await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                        this.env.model.root.records
                    );
                    this.bankReconciliation.reloadChatter();
                    this.restoreFocus();
                },
            },
            {
                onClose: () => {
                    this.restoreFocus();
                },
            }
        );
    }

    /**
     * Opens a dialog to select an account and assigns it to the current reconcile line.
     */
    setAccountOnReconcileLine() {
        const context = {
            list_view_ref: "account_accountant.view_account_list_bank_rec_widget",
            search_view_ref: "account_accountant.view_account_search_bank_rec_widget",
            ...(this.statementLineData.amount > 0
                ? { preferred_account_type: "income" }
                : { preferred_account_type: "expense" }),
        };

        this.addDialog(
            SelectCreateDialog,
            {
                title: _t("Search: Account"),
                noCreate: true,
                multiSelect: false,
                domain: [
                    [
                        "id",
                        "not in",
                        [
                            this.statementLineData.journal_id.suspense_account_id.id,
                            this.statementLineData.journal_id.default_account_id.id,
                        ],
                    ],
                ],
                context: context,
                resModel: "account.account",
                onSelected: async (account) => {
                    // After setting an account on a line, a new reconciliation model may be automatically created. If so,
                    // we need to reload the records that will use this model to make sure the new model is displayed.
                    const linesToLoad = await this._setAccountOnReconcileLine(
                        this.lastAccountMoveLine.data.id,
                        account[0],
                        { context: { account_default_taxes: true } }
                    );
                    const recordsToLoad = [
                        ...this.env.model.root.records.filter((record) =>
                            linesToLoad.includes(record.data.id)
                        ),
                        this.props.statementLine,
                    ];
                    await this.bankReconciliation.reloadRecords(recordsToLoad);
                    this.bankReconciliation.reloadChatter();
                    this.restoreFocus();
                },
            },
            {
                onClose: () => {
                    this.restoreFocus();
                },
            }
        );
    }

    /**
     * Assigns the given account to a specific account move line within the current bank statement line.
     *
     * @param {number} amlId - ID of the account move line to update.
     * @param {number} accountId - ID of the selected account to assign.
     * @param {Object} context - the context to use for adding default tax of account
     *
     * @returns {Promise<list>} - The list of IDs of lines to reload in case of auto-rule creation.
     */
    async _setAccountOnReconcileLine(amlId, accountId, context = {}) {
        return await this.orm.call(
            "account.bank.statement.line",
            "set_account_bank_statement_line",
            [this.statementLineData.id, amlId, accountId],
            context
        );
    }

    /**
     * Sets the account receivable on the current reconcile line.
     */
    async setAccountReceivableOnReconcileLine() {
        let accountId;
        if (this.statementLineData.partner_id.property_account_receivable_id.id) {
            accountId = this.statementLineData.partner_id.property_account_receivable_id.id;
        } else {
            accountId = await this.orm.webSearchRead("account.account", [
                ["account_type", "=", "asset_receivable"],
            ]);
        }
        await this._setAccountOnReconcileLine(this.lastAccountMoveLine.data.id, accountId);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    /**
     * Sets the account payable on the current reconcile line..
     */
    async setAccountPayableOnReconcileLine() {
        let accountId;
        if (this.statementLineData.partner_id.property_account_payable_id.id) {
            accountId = this.statementLineData.partner_id.property_account_payable_id.id;
        } else {
            accountId = await this.orm.webSearchRead("account.account", [
                ["account_type", "=", "liability_payable"],
            ]);
        }
        await this._setAccountOnReconcileLine(this.lastAccountMoveLine.data.id, accountId);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    /**
     * Opens a dialog to search and select journal items to reconcile with the current bank statement line.
     */
    reconcileOnReconcileLine() {
        const context = {
            list_view_ref: "account_accountant.view_account_move_line_list_bank_rec_widget",
            search_view_ref: "account_accountant.view_account_move_line_search_bank_rec_widget",
            preferred_aml_value: -this.props.suspenseAccountLine.amount_currency,
            preferred_aml_currency_id: this.props.suspenseAccountLine.currency_id.id,
            ...(this.statementLineData.partner_id
                ? { search_default_partner_id: this.statementLineData.partner_id.id }
                : { search_default_posted: 1 }),
        };

        this.addDialog(
            BankRecSelectCreateDialog,
            {
                title: _t("Search: Journal Items to Match"),
                noCreate: true,
                domain: this.getReconcileButtonDomain(),
                resModel: "account.move.line",
                size: "xl",
                context: context,
                onSelected: async (moveLines) => {
                    await this.orm.call(
                        "account.bank.statement.line",
                        "set_line_bank_statement_line",
                        [this.statementLineData.id, moveLines]
                    );
                    await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                        this.env.model.root.records
                    );
                    this.props.statementLine.load();
                    this.bankReconciliation.reloadChatter();
                    this.restoreFocus();
                },
                suspenseAccountLine: this.props.suspenseAccountLine,
                reference: this.statementLineData.payment_ref,
                date: this.statementLineData.date,
            },
            {
                onClose: () => {
                    this.restoreFocus();
                },
            }
        );
    }

    getReconcileButtonDomain() {
        return [
            ["parent_state", "in", ["draft", "posted"]],
            ["company_id", "child_of", this.statementLineData.company_id.id],
            ["search_account_id.reconcile", "=", true],
            ["display_type", "not in", ["line_section", "line_note"]],
            ["reconciled", "=", false],
            "|",
            ["search_account_id.account_type", "not in", ["asset_receivable", "liability_payable"]],
            ["payment_id", "=", false],
            ["statement_line_id", "!=", this.statementLineData.id],
        ];
    }

    /**
     * Deletes the current bank statement line.
     */
    async deleteTransaction() {
        this.addDialog(ConfirmationDialog, {
            body: _t("Are you sure you want to delete this statement line?"),
            confirm: async () => {
                await this.orm.unlink("account.bank.statement.line", [this.statementLineData.id]);
                this.env.model.load();
            },
            cancel: () => {},
        });
    }

    /**
     * Set the move of the statement line as to check
     */
    async setStatementLineAsReviewed() {
        await this.orm.call("account.move", "set_moves_checked", [
            this.statementLineData.move_id.id,
        ]);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    // -----------------------------------------------------------------------------
    // Reconciliation Model
    // -----------------------------------------------------------------------------
    /**
     * Applies a reconciliation model to the current bank statement line.
     *
     * @param {number} reconciliationModelId - The ID of the reconciliation model to apply.
     */
    async triggerReconciliationModel(reconciliationModelId) {
        await this.orm.call("account.reconcile.model", "trigger_reconciliation_model", [
            reconciliationModelId,
            this.statementLineData.id,
        ]);
        await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
            this.env.model.root.records
        );
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    /**
     * Retrieves the corresponding action, condition, and button element for a given key.
     * This function is part of a keydown event handler that maps specific key presses to actions
     * on the reconciliation line, such as setting a partner or reconciling an account.
     * It checks if a line is selected and if the relevant button exists before returning the action details.
     *
     * @param {string|number} key - The key pressed.
     * @returns {Object|undefined} An object containing the action, condition, and button element, or undefined if no action is found.
     */
    getKeyAction(key) {
        const keyActions = {
            1: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".set-partner-btn") &&
                    this.isLineSelected,
                action: async () => this.setPartnerOnReconcileLine(),
                buttonElement: this.props.statementLineRootRef.el.querySelector(".set-partner-btn"),
            },
            2: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".reconcile-btn") &&
                    this.isLineSelected,
                action: async () => this.reconcileOnReconcileLine(),
                buttonElement: this.props.statementLineRootRef.el.querySelector(".reconcile-btn"),
            },
            3: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".set-account-btn") &&
                    this.isLineSelected,
                action: () => this.setAccountOnReconcileLine(),
                buttonElement: this.props.statementLineRootRef.el.querySelector(".set-account-btn"),
            },
            4: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".set-payable-btn") &&
                    this.isLineSelected,
                action: () => this.setAccountPayableOnReconcileLine(),
                buttonElement: this.props.statementLineRootRef.el.querySelector(".set-payable-btn"),
            },
            5: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".set-receivable-btn") &&
                    this.isLineSelected,
                action: () => this.setAccountReceivableOnReconcileLine(),
                buttonElement:
                    this.props.statementLineRootRef.el.querySelector(".set-receivable-btn"),
            },
            6: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-0"
                    ) && this.isLineSelected,
                action: () => {
                    const buttonElement = this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-0"
                    );
                    if (buttonElement) {
                        buttonElement.click();
                    }
                },
                buttonElement: this.props.statementLineRootRef.el.querySelector(
                    ".reconciliation-model-btn-0"
                ),
            },
            7: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-1"
                    ) && this.isLineSelected,
                action: () => {
                    const buttonElement = this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-1"
                    );
                    if (buttonElement) {
                        buttonElement.click();
                    }
                },
                buttonElement: this.props.statementLineRootRef.el.querySelector(
                    ".reconciliation-model-btn-1"
                ),
            },
            8: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-2"
                    ) && this.isLineSelected,
                action: () => {
                    const buttonElement = this.props.statementLineRootRef.el.querySelector(
                        ".reconciliation-model-btn-2"
                    );
                    if (buttonElement) {
                        buttonElement.click();
                    }
                },
                buttonElement: this.props.statementLineRootRef.el.querySelector(
                    ".reconciliation-model-btn-2"
                ),
            },
            Enter: {
                condition:
                    this.props.statementLineRootRef.el.querySelector(".btn-primary") &&
                    this.isLineSelected,
                action: () => {
                    const primaryButtons = this.props.statementLineRootRef.el.querySelectorAll(".btn-primary");
                    if (primaryButtons.length > 0) {
                        primaryButtons[0].click();
                    }
                },
                buttonElement: this.props.statementLineRootRef.el.querySelector(".btn-primary"),
            },
        };
        return keyActions[key];
    }

    /**
     * Registers hotkeys for the reconciliation buttons.
     */
    registerHotkeys() {
        const hotkeyConfigs = [
            { key: "1", trigger: "alt+shift+1" },
            { key: "2", trigger: "alt+shift+2" },
            { key: "3", trigger: "alt+shift+3" },
            { key: "4", trigger: "alt+shift+4" },
            { key: "5", trigger: "alt+shift+5" },
            { key: "6", trigger: "alt+shift+6" },
            { key: "7", trigger: "alt+shift+7" },
            { key: "8", trigger: "alt+shift+8" },
            { key: "Enter", trigger: "alt+shift+enter" },
        ];
        hotkeyConfigs.forEach(({ key, trigger }) => {
            useHotkey(
                trigger,
                ({ target }) => {
                    const { condition, action } = this.getKeyAction(key);
                    if (condition) {
                        action();
                    }
                },
                {
                    area: () => this.props.statementLineRootRef.el.parentElement,
                    withOverlay: () => {
                        const { buttonElement, condition } = this.getKeyAction(key);
                        return condition ? buttonElement : null;
                    },
                    isAvailable: () => {
                        const { condition } = this.getKeyAction(key);
                        return condition;
                    },
                }
            );
        });
    }

    // -----------------------------------------------------------------------------
    // File Uploader
    // -----------------------------------------------------------------------------
    get bankRecFileUploaderRecord() {
        return {
            statementLineId: this.statementLineData.id,
        };
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------
    actionViewRecoModels() {
        return this.action.doAction("account.action_account_reconcile_model");
    }

    // -----------------------------------------------------------------------------
    // GETTER
    // -----------------------------------------------------------------------------
    get statementLineData() {
        return this.props.statementLine.data;
    }

    get isLineSelected() {
        return this.statementLineData.id === this.bankReconciliation.statementLine?.data.id;
    }

    get lastAccountMoveLine() {
        return this.statementLineData.line_ids.records.at(-1);
    }

    get isCustomerRankHigher() {
        return (
            this.statementLineData.partner_id.customer_rank >
            this.statementLineData.partner_id.supplier_rank
        );
    }

    get isSetPartnerButtonShown() {
        return !this.statementLineData.partner_id;
    }

    get isSetAccountButtonShown() {
        return !this.statementLineData.account_id;
    }

    get isSetReceivableButtonShown() {
        return (
            !this.isSetPartnerButtonShown &&
            ((this.statementLineData.partner_id.customer_rank && this.isCustomerRankHigher) ||
                this.statementLineData.amount > 0)
        );
    }

    get isSetPayableButtonShown() {
        return (
            !this.isSetPartnerButtonShown &&
            ((this.statementLineData.partner_id.supplier_rank && !this.isCustomerRankHigher) ||
                this.statementLineData.amount < 0)
        );
    }

    get isReconcileButtonShown() {
        // Show the button if we have more than one reconciliable line
        // or if we didn't compute it yet
        return this.props.reconcileLineCount === null || this.props.reconcileLineCount;
    }

    get reconcileModelsInDropdown() {
        if (this.ui.isSmall) {
            return this.props.reconcileModels;
        }
        return this.props.reconcileModels.filter(
            (model) => model.id !== this.props?.preSelectedReconciliationModel?.id
        );
    }

    /**
     * Dynamically builds the list of action buttons to be shown in the reconciliation interface.
     *
     * @returns {Object} buttonsToDisplay - A dictionary of buttons to render in the UI.
     */
    get buttons() {
        const buttonsToDisplay = {};
        if (this.isSetPartnerButtonShown) {
            buttonsToDisplay.partner = {
                label: _t("Set Partner"),
                action: this.setPartnerOnReconcileLine.bind(this),
                classes: "set-partner-btn",
            };
        } else {
            buttonsToDisplay.receivable = {
                label: _t("Receivable"),
                action: this.setAccountReceivableOnReconcileLine.bind(this),
                classes: "set-receivable-btn",
            };
            buttonsToDisplay.payable = {
                label: _t("Payable"),
                action: this.setAccountPayableOnReconcileLine.bind(this),
                classes: "set-payable-btn",
            };
        }

        if (this.isReconcileButtonShown) {
            buttonsToDisplay.reconcile = {
                label: _t("Reconcile"),
                action: this.reconcileOnReconcileLine.bind(this),
                count: this.props.reconcileLineCount,
                classes: "reconcile-btn",
            };
        }

        if (this.isSetAccountButtonShown) {
            buttonsToDisplay.account = {
                label: _t("Set Account"),
                action: this.setAccountOnReconcileLine.bind(this),
                classes: "set-account-btn",
            };
        }

        if (this.statementLineData.is_reconciled && !this.statementLineData.checked) {
            buttonsToDisplay.toReview = {
                label: _t("Reviewed"),
                action: this.setStatementLineAsReviewed.bind(this),
                toReview: true,
            };
        }

        return buttonsToDisplay;
    }

    /**
     * Prioritizing which buttons are shown and which one is marked as "primary".
     *
     * @returns {Array<Object>} An array of button objects, each with label, action, and optionally `primary`.
     */
    get buttonsToDisplay() {
        const buttons = this.buttons || {};

        let primaryButtonKeys = [];
        let secondaryButtonKeys = [];
        if (buttons?.partner && buttons?.account) {
            primaryButtonKeys = ["partner", "account"];
        } else if (buttons?.reconcile && !!buttons.reconcile?.count) {
            primaryButtonKeys = ["reconcile"];
            if (this.isSetReceivableButtonShown) {
                secondaryButtonKeys = ["receivable"];
            } else {
                secondaryButtonKeys = ["payable"];
            }
        } else if (this.isSetReceivableButtonShown) {
            primaryButtonKeys = ["receivable"];
        } else if (this.isSetPayableButtonShown) {
            primaryButtonKeys = ["payable"];
        }

        return [
            ...primaryButtonKeys.map((key) => ({ ...buttons[key], primary: true })),
            ...secondaryButtonKeys.map((key) => ({ ...buttons[key] })),
        ];
    }

    get buttonsInDropdown() {
        const buttons = this.buttons || {};
        if (this.props.preSelectedReconciliationModel) {
            return Object.values(buttons);
        }
        const buttonToDisplayClasses = this.buttonsToDisplay.map((button) => button.classes) || [];
        // Get all other buttons excluding primary ones
        return Object.values(buttons).filter(
            (button) => !buttonToDisplayClasses.includes(button.classes)
        );
    }
}
