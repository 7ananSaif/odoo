import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BankRecReconcileDialogListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onSelectionChanged() {
        const resIds = await this.model.root.getResIds(true);
        if (!resIds.length) {
            this.props.onSelectionChanged(resIds, []);
        }

        let selectedLines;
        // When being in the list view with more element than the limit and doing a select all, the user has the
        // possibility to select more element than the limit. In this case the isDomainSelected is True
        if (this.isDomainSelected) {
            const { resModel, context } = this.model.root._config;
            selectedLines = await this.orm.read(
                resModel,
                resIds,
                ["amount_residual", "amount_residual_currency", "currency_id"],
                { context }
            );
        } else {
            selectedLines = Object.values(this.model.root.records)
                .filter((record) => resIds.includes(record._config.resId))
                .map((record) => {
                    const data = record.data;
                    return {
                        amount_residual: data.amount_residual,
                        amount_residual_currency: data.amount_residual_currency,
                        currency_id: data.currency_id.id,
                    };
                });
        }
        this.props.onSelectionChanged(resIds, selectedLines);
    }
}

export class BankRecReconcileDialogListRenderer extends ListRenderer {
    static template = "account_accountant.BankRecReconcileDialogListRenderer";
    static recordRowTemplate = "account_accountant.BankRecReconcileDialogListRenderer.RecordRow";

    async openMoveView(record) {
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: record.data.move_id.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const bankRecReconcileDialogListRenderer = {
    ...listView,
    Renderer: BankRecReconcileDialogListRenderer,
    Controller: BankRecReconcileDialogListController,
};

registry.category("views").add("bank_rec_dialog_list", bankRecReconcileDialogListRenderer);
