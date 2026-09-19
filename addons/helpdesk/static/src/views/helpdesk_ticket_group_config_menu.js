import { useService } from "@web/core/utils/hooks";
import { GroupConfigMenu } from "@web/views/view_components/group_config_menu";

export class HelpdeskTicketGroupConfigMenu extends GroupConfigMenu {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    async deleteGroup() {
        if (this.group.groupByField.name === "stage_id") {
            const action = await this.group.model.orm.call(
                this.group.groupByField.relation,
                "action_unlink_wizard",
                [this.group.value],
                { context: this.group.context }
            );
            this.action.doAction(action);
            return;
        }
        super.deleteGroup();
    }
}
