import { Component, onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { dashboardActionRegistry } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_action";
import { _t } from "@web/core/l10n/translation";

export class DashboardEdit extends Component {
    static template = "spreadsheet_dashboard_edition.DashboardEdit";
    static props = {
        onClick: Function,
        dashboardId: Number,
        data: Object,
    };
    setup() {
        this.isDashboardAdmin = false;
        onWillStart(async () => {
            if (this.env.debug) {
                this.isDashboardAdmin = await user.hasGroup(
                    "spreadsheet_dashboard.group_dashboard_manager"
                );
            }
        });
    }
    onClick() {
        return this.props.onClick(this.props.dashboardId);
    }

    get tooltip() {
        return this.props.data.is_from_data
            ? _t(
                  "Editing standard dashboards is not recommended. Changes will be lost on Odoo upgrades."
              )
            : _t("Edit");
    }
}

dashboardActionRegistry.add("dashboard_edit", DashboardEdit);
