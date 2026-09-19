import { useService, useBus } from "@web/core/utils/hooks";
import { isNull } from "@web/views/utils";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import {AccountReturnKanbanRecord} from "./account_return_kanban_record";
import { AccountReturnBaseKanbanRenderer } from "./account_return_base_kanban_renderer";


export class AccountReturnKanbanRenderer extends AccountReturnBaseKanbanRenderer {
    static template="account_reports.account_return_kanban_renderer";

    static props = [
        ...KanbanRenderer.props,
    ]

    static components = {
        ...KanbanRenderer.components,
        AccountReturnKanbanRecord
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");

        useBus(this.env.bus, "return_reload_model", (ev) => {
            const recordIds = ev.detail.resIds;
            let recordToReload = this.records.filter((record) => recordIds.includes(record.resId));
            for (let record of recordToReload) {
                record.model.load();
            }
        });
    }

    async openRecord(record, params) {
        if (record.context?.in_checks_view) {
            return
        }
        const action = await this.orm.call("account.return", "action_open_account_return", [record.resIds]);
        if (!action)
            return
        return this.actionService.doAction(action);
    }

    get records() {
        const { list } = this.props;
        if (list.isGrouped) {
            return list.groups.flatMap((group) => group.list.records);
        }
        else {
            return list.records;
        }
    }

    get groups() {
        const { list } = this.props;
        if (!list.isGrouped) {
            return false;
        }

        return list.groups.map((group, i) => ({
            ...group,
            key: isNull(group.value) ? `group_key_${i}` : String(group.value),
        }));
    }
}
