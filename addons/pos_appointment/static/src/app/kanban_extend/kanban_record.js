import { Component } from "@odoo/owl";
import { isHtmlEmpty } from "@web/core/utils/html";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { usePopover } from "@web/core/popover/popover_hook";
import { _t } from "@web/core/l10n/translation";

export class PosAppointmentKanbanPopover extends Component {
    static props = { "*": { optional: true } };
    static template = "pos_restaurant_appointment.PosAppointmentKanbanPopover";

    setup() {
        super.setup(...arguments);
        this.isHtmlEmpty = isHtmlEmpty;
    }

    async loadData() {
        const root = this.props.record.model.root;
        const { limit, offset } = root;
        await root.load({ offset, limit });
    }

    async onclickAppointmentStatus(status) {
        this.props.record.update(
            {
                appointment_status: status,
                active: status === "cancelled" ? false : true,
            },
            { save: true }
        );
        await this.loadData();
    }

    async onClickEdit() {
        const action = await this.props.orm.call(
            "calendar.event",
            "action_open_booking_form_view",
            [[this.props.record.data.id]]
        );
        return this.props.action.doAction(action, {
            onClose: async () => {
                await this.loadData();
            },
        });
    }

    getButtonClass(status) {
        const classMap = {
            booked: "o_kanban_color_2",
            attended: "o_kanban_color_10",
            no_show: "o_kanban_color_1",
        };
        return this.props.record.data.appointment_status === status ? `${classMap[status]}` : "";
    }

    get buttons() {
        return [
            { status: "cancelled", label: _t("Delete"), extraClass: "text-bg-danger" },
            { status: "booked", label: _t("Booked"), extraClass: "ms-4" },
            { status: "attended", label: _t("Check In"), extraClass: "" },
            { status: "no_show", label: _t("No Show"), extraClass: "" },
        ];
    }
}

export class PosKanbanRecord extends KanbanRecord {
    static template = "pos_restaurant_appointment.KanbanRecord";

    setup() {
        super.setup(...arguments);
        this.popover = usePopover(PosAppointmentKanbanPopover, { position: "bottom" });
    }

    onInfoClick(ev) {
        this.popover.open(ev.currentTarget, {
            record: this.props.record,
            close: this.popover.close,
            orm: this.props.record.model.orm,
            action: this.props.record.model.action,
            resId: this.props.record._config.resId,
        });
    }
}
