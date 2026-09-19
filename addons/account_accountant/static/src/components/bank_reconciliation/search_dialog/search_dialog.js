import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { formatMonetary } from "@web/views/fields/formatters";
import { useService } from "@web/core/utils/hooks";

const { DateTime } = luxon;

export class BankRecSelectCreateDialog extends SelectCreateDialog {
    static template = "account_accountant.BankRecSelectCreateDialog";
    static props = {
        ...SelectCreateDialog.props,
        suspenseAccountLine: Object,
        reference: String,
        date: DateTime,
        size: { type: String, optional: true },
    };

    static defaultProps = {
        ...SelectCreateDialog.defaultProps,
        size: "lg",
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.state.remainingAmount = this.suspenseAccountLine.amount_currency;
        this.state.hideRemainingAmount = false;

        this.baseViewProps.onSelectionChanged = (resIds, selectedLines) => {
            this.state.resIds = resIds;
            this.changeInSelectedMoveLine(selectedLines);
        };
    }

    async changeInSelectedMoveLine(selectedLines) {
        if (!selectedLines?.length) {
            this.state.remainingAmount = this.suspenseAccountLine.amount_currency;
            return;
        }

        let selectedLinesSum = 0;
        this.state.hideRemainingAmount = false;
        // When the suspense currency is different from the company one, we cannot compute the remaining amount correctly
        // due to the currency rates. So in this case, when the user select multiple currencies we add the remaining amount
        if (
            this.suspenseAccountLine.currency_id.id !==
            this.suspenseAccountLine.company_currency_id.id
        ) {
            const selectedLineCurrencies = selectedLines.map((line) => line.currency_id);

            if (
                selectedLineCurrencies.length !== 1 ||
                (selectedLineCurrencies.length === 1 &&
                    selectedLineCurrencies[0] !== this.suspenseAccountLine.currency_id.id)
            ) {
                this.state.hideRemainingAmount = true;
                return;
            } else {
                selectedLinesSum = selectedLines.reduce((sum, line) => {
                    return sum + line.amount_residual_currency;
                }, 0);
            }
        } else {
            selectedLinesSum = selectedLines.reduce((sum, line) => {
                return sum + line.amount_residual;
            }, 0);
        }
        this.state.remainingAmount = this.suspenseAccountLine.amount_currency + selectedLinesSum;
    }

    get suspenseAccountLine() {
        return this.props?.suspenseAccountLine;
    }

    get remainingAmountFormatted() {
        return formatMonetary(this.state.remainingAmount, {
            currencyId: this.suspenseAccountLine.currency_id.id,
        });
    }

    get formattedStatementLineDate() {
        return this.props.date?.toLocaleString();
    }
}
