import { Component } from "@odoo/owl";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { useService } from "@web/core/utils/hooks";
import { x2ManyCommands } from "@web/core/orm_service";

export class BankRecReconciledLineName extends Component {
    static template = "account_accountant.BankRecReconciledLineName";
    static props = {
        statementLine: { type: Object },
        linesToReconcile: { type: Object },
        moveLineId: { type: String },
        valueToDisplay: { type: Object },
    };

    setup() {
        this.orm = useService("orm");
        this.bankReconciliation = useBankReconciliation();
    }

    async deleteTax(lineId, taxChanged) {
        const lineData = this.props.linesToReconcile.filter((line) => {
            return line.id === parseInt(lineId);
        })[0];
        await this.orm.call("account.bank.statement.line", "edit_reconcile_line", [
            this.props.statementLine.data.id,
            lineData.id,
            { tax_ids: [[x2ManyCommands.UNLINK, taxChanged.data.id]] },
        ]);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }
}
