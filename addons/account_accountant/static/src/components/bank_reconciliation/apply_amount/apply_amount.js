import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class BankRecWidgetApplyAmountHtmlField extends Component {
    static props = standardFieldProps;
    static template = "account_accountant.BankRecWidgetApplyAmountHtmlField";

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    async switchApplyAmount(ev) {
        const root = this.env.model.root;
        const fetchReconciledLines = async (fields = []) => {
            return await this.orm.searchRead(
                "account.move.line",
                [
                    [
                        "id",
                        "in",
                        ...root.data.reconciled_lines_excluding_exchange_diff_ids._currentIds,
                    ],
                ],
                fields
            );
        };

        const fetchStatementLines = async (fields = []) => {
            return await this.orm.searchRead(
                "account.move.line",
                [["move_id", "=", root.data.move_id.id]],
                fields
            );
        };

        if (ev.target.attributes.name?.value === "action_redirect_to_move") {
            const [line] = await fetchReconciledLines(["amount_currency", "balance", "move_id"]);
            await this.openMove(line.move_id[0]);
        } else if (ev.target.attributes.name?.value === "apply_full_amount") {
            const [line] = await fetchReconciledLines(["amount_currency", "balance"]);
            await root.update({
                balance: -line.balance,
                amount_currency: -line.amount_currency,
            });
        } else if (ev.target.attributes.name?.value === "apply_partial_amount") {
            const lines = await fetchStatementLines(["amount_currency", "balance"]);
            // We have all the lines of the entry, we want the amount of the suspense line
            await root.update({
                balance: lines.at(-1).balance,
                amount_currency: lines.at(-1).amount_currency,
            });
        }
    }

    openMove(moveId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: moveId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

const bankRecWidgetApplyAmountHtmlField = { component: BankRecWidgetApplyAmountHtmlField };

registry.category("fields").add("apply_amount_html", bankRecWidgetApplyAmountHtmlField);
