import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { useAuditBalanceListChatterService } from "./account_audit_balance_list_chatter_service";
import { onWillStart } from "@odoo/owl";

export class AccountAuditBalanceListController extends ListController {
    static template = "account_reports.account_audit_balance_list_controller";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.chatterService = useAuditBalanceListChatterService();

        onWillStart(async () => {
            const working_file_id = this.props.context?.working_file_id;
            if (!working_file_id) {
                return;
            }

            const working_file = await this.orm.searchRead(
                "account.return",
                [["id", "=", working_file_id]],
                ["date_to"],
                { limit: 1 }
            );
            if (working_file.length === 1) {
                this.chatterService.chatterState.date_to = working_file[0]?.date_to;
            }
        });
    }

    openJournalItems() {
        this.actionService.doActionButton({
            context: this.model.root.context,
            resModel: this.model.root.resModel,
            name: "action_audit_account",
            type: "object",
            resIds: this.model.root.selection.map((record) => record.data.code),
        });
    }
}
