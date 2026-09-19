import { _t } from "@web/core/l10n/translation";
import { HrGanttRenderer } from "@hr_gantt/hr_gantt_renderer";
import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { GanttController } from "@web_gantt/gantt_controller";

export class HrHolidaysGanttRenderer extends HrGanttRenderer {
    static components = {
        ...HrGanttRenderer.components,
    };
    static pillTemplate = "hr_holidays_gantt.GanttRenderer.Pill";
}

export class HrHolidaysGanttOverviewRenderer extends HrHolidaysGanttRenderer {
    setup() {
        super.setup();
        onWillStart(async() => {
            this.hasHrHolidaysRight = await user.hasGroup("hr_holidays.group_hr_holidays_responsible");
        });
    }

    async onPillClicked(ev, pill) {
        const popoverProps = await this.getPopoverProps(pill);
        popoverProps.buttons.find((el) => el.id === "open_view_edit_dialog").onClick();
    }
}

export class HrHolidaysGanttController extends GanttController {
    /** @override */
    openDialog(props, options) {
        super.openDialog({
            ...props,
            title: _t("Time Off Request"),
            size: "md",
            canExpand: false,
        }, options);
    }
}

export class HrHolidaysGanttManagerHrLeaveController extends HrHolidaysGanttController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        onWillStart(async () => {
            this.canCreateGroupTimeOff = await user.hasGroup("hr_holidays.group_hr_holidays_responsible");
        });
    }

    async onNewGroupTimeOff() {
        await this.actionService.doAction("hr_holidays.action_hr_leave_generate_multi_wizard");
    }
}

export const hrHolidaysGanttManagerView = {
    ...hrGanttView,
    Renderer: HrHolidaysGanttRenderer,
};

export const hrHolidaysGanttManagerHrLeaveView = {
    ...hrHolidaysGanttManagerView,
    Controller: HrHolidaysGanttManagerHrLeaveController,
    buttonTemplate: "hr_holidays_gantt.GanttView.Buttons",
};

export const hrHolidaysGanttView = {
    ...hrGanttView,
    Renderer: HrHolidaysGanttOverviewRenderer,
    Controller: HrHolidaysGanttController,
};

registry.category("views").add("hr_holidays_gantt_manager", hrHolidaysGanttManagerView);
registry.category("views").add("hr_holidays_gantt_manager_hr_leave", hrHolidaysGanttManagerHrLeaveView);
registry.category("views").add("hr_holidays_gantt", hrHolidaysGanttView);
