import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from '@web/core/registry';
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

export class AppointmentQuickShareButton extends Component {
    static props = {
        ...standardWidgetProps,
    };
    static template = "appointment.appointmentQuickShareButton";

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
    }

    async onClickShareBtn() {
        const bookUrl = await this.orm.call(
            "appointment.type",
            "get_kanban_record_share_btn_url",
            [this.props.record.resId]
        );

        setTimeout(async () => {
            await browser.navigator.clipboard.writeText(bookUrl);
            this.notification.add(
                _t("Link copied to clipboard!"),
                { type: "success" }
            );
        });
    }
}

export const appointmentQuickShareButton = {
    component: AppointmentQuickShareButton,
};

registry.category("view_widgets").add("appointment_quick_share_button", appointmentQuickShareButton);
