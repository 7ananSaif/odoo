import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";

export class TransientBankStatementLineListController extends ListController {

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    async onClickImportTransactions() {
        const resIds = await this.model.root.getResIds(true);
        const resultAction = await this.orm.call("account.bank.statement.line.transient", "action_import_transactions", [resIds]);
        this.action.doAction(resultAction);
    }

    get allowImportTransaction() {
        return !this.props.context.disable_import;
    }
}

export class TransientBankStatementLineListRenderer extends ListRenderer {

    static template = "account_online_synchronization.TransientBankStatementLineRenderer";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    async openManualEntries() {
        if (this.env.searchModel.context.active_model === "account.missing.transaction.wizard" && this.env.searchModel.context.active_ids) {
            const activeIds = this.env.searchModel.context.active_ids;
            const action = await this.orm.call("account.missing.transaction.wizard", "action_open_manual_bank_statement_lines", activeIds);
            this.action.doAction(action);
        }
    }

    async openCancelledEntries() {
        if (
            this.env.searchModel.context.active_model === "account.missing.transaction.wizard" &&
            this.env.searchModel.context.active_ids
        ) {
            return await this.action.doActionButton({
                name: "action_open_cancelled_bank_statement_lines",
                type: "object",
                resModel: "account.missing.transaction.wizard",
                resIds: this.env.searchModel.context.active_ids,
            });
        }
    }
}

export const TransientBankStatementLineListView = {
    ...listView,
    Renderer: TransientBankStatementLineListRenderer,
    Controller: TransientBankStatementLineListController,
    buttonTemplate: "TransientBankStatementLineButtonTemplate",
}

registry.category("views").add("transient_bank_statement_line_list_view", TransientBankStatementLineListView);
