import { patch } from "@web/core/utils/patch";
import { useOwnedDialogs } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { SpreadsheetSelectorPanel } from "@spreadsheet_edition/assets/components/spreadsheet_selector_dialog/spreadsheet_selector_panel";

patch(SpreadsheetSelectorPanel.prototype, {
    setup() {
        super.setup();
        this.addDialog = useOwnedDialogs();
    },

    _isDashboardModel() {
        return this.props.model === "spreadsheet.dashboard";
    },

    get blankCardLabel() {
        return this._isDashboardModel() ? _t("Blank dashboard") : super.blankCardLabel;
    },

    async _getCreateAndOpenDashboardAction() {
        return new Promise((resolve, reject) => {
            this.addDialog(FormViewDialog, {
                resModel: "spreadsheet.dashboard",
                title: _t("Create a New Dashboard"),
                context: {
                    form_view_ref:
                        "spreadsheet_dashboard_edition.spreadsheet_dashboard_creation_dialog_view_form",
                },
                canExpand: false,
                onRecordSaved: async (record) => {
                    const action = await this.orm.call(
                        this.props.model,
                        "action_open_spreadsheet",
                        [[record.resId]]
                    );
                    action.params ??= {};
                    action.params.is_new_spreadsheet = true;
                    resolve(action);
                },
                onRecordDiscarded: resolve,
            });
        });
    },

    _getActionForSelectedItem(spreadsheet) {
        if (!spreadsheet && this._isDashboardModel()) {
            return this._getCreateAndOpenDashboardAction;
        }
        return super._getActionForSelectedItem(spreadsheet);
    },
});
