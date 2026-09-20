import { Component } from "@odoo/owl";

export class BankRecStatementSummary extends Component {
    static template = "account_accountant.BankRecStatementSummary";

    static props = {
        label: { type: String },
        amount: { type: String, optional: true },
        action: { type: Function },
        journalId: { type: Number, optional: true },
        isValid: { type: Boolean, optional: true },
        journalIsInvalid: { type: Boolean, optional: true },
    };
    static defaultProps = {
        isValid: true,
    };

    actionApplyInvalidStatement() {
        const facets = this.env.searchModel.facets;
        const searchItems = this.env.searchModel.searchItems;
        const invalidStatementFilter = Object.values(searchItems).find(
            (i) => i.name == "invalid_statement"
        );
        const invalidStatementFacet = facets.filter(
            (i) => i.groupId == invalidStatementFilter.groupId
        );
        if (
            invalidStatementFacet.length == 0 || 
            !invalidStatementFacet[0].values.includes(invalidStatementFilter.description)
        ){
            this.env.searchModel.toggleSearchItem(invalidStatementFilter.id);
        }
    }
}
