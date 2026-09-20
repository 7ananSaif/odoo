import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormRenderer } from "@web/views/form/form_renderer";

import { ExtractMixinFormRenderer } from '@iap_extract/components/manual_correction/form_renderer';


export class AccountBankStatementFormRenderer extends ExtractMixinFormRenderer(FormRenderer) {
    setup() {
        super.setup();

        this.recordModel = 'account.bank.statement';
    }

    /**
     * @override ExtractMixinFormRenderer
     */
    async getNewRecordValues(record, line, field) {
        const createValues = await super.getNewRecordValues(...arguments);
        if (field != 'date') {
            // If the field used to create the record isn't the date, try to guess it.
            // The date field is required on bank statement line, so we try to set it.

            // Find the date boxes that are aligned
            let dateVal = undefined;
            const pageNumber = line.page;
            const dateBoxes = this.unskewBoxes(this.boxes['date'][pageNumber] || [], this.skewAngles[pageNumber]);
            const matchingDateBoxes = dateBoxes.filter((dateBox) => {
                return this.isPartOfLine(line, dateBox);
            });
            if (matchingDateBoxes.length === 1) {
                dateVal = this.getValueFromBoxes(matchingDateBoxes, 'date');
            }
            else if (this.props.record.data.date) {
                // If not aligned date, use the bank statement date
                dateVal = this.props.record.data.date;
            }
            else {
                // Last resort, use create date
                dateVal = this.props.record.data.create_date;
            }
            createValues['date'] = dateVal;
        }
        return createValues;
    }
};


export const AccountBankStatementFormViewExtract = {
    ...formView,
    Renderer: AccountBankStatementFormRenderer,
};

registry.category("views").add("account_bank_statement_form", AccountBankStatementFormViewExtract);
