import { _t } from "@web/core/l10n/translation";
import {
    deleteConfirmationMessage,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";

export class GoalTemplateDeleteConfirmationDialog extends ConfirmationDialog {
    static template = "hr_appraisal.GoalTemplateDeleteConfirmationDialog";

    static props = {
        ...ConfirmationDialog.props,
        hasChildren: Boolean,
        confirmAllLabel: { type: String, optional: true },
        confirmAll: Function,
    }

    static defaultProps = {
        ...ConfirmationDialog.defaultProps,
        title: _t("Bye-bye, record!"),
        body: deleteConfirmationMessage,
        confirmLabel: _t("Delete"),
        confirmAllLabel: _t("Delete with children"),
        cancel: () => {
            // `ConfirmationDialog` needs this prop to display the cancel
            // button but we do nothing on cancel.
        },
        cancelLabel: _t("No, keep it"),
    };
}
