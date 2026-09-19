import { DocumentFileUploader } from "@account/components/document_file_uploader/document_file_uploader";

export class BankRecFileUploader extends DocumentFileUploader {

    /**
     * This method extends the DocumentFileUploader `getExtraContext` to add the `statement_line_id` to the context,
     * which is useful for passing the current statement line ID to other components or services. This will be useful
     * for the 'create_document_from_attachment' method (in account_bank_statement.py).
     *
     * @returns {Object} The extended context object with the `statement_line_id`.
     */
    getExtraContext() {
        const extraContext = super.getExtraContext();
        return {
            ...extraContext,
            statement_line_id: this.props.record.statementLineId,
        };
    }

    getResModel() {
        return "account.bank.statement.line";
    }
}
