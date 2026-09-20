import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export class AccessRightsUpdateConfirmationDialog extends ConfirmationDialog {
    static template = "documents.AccessRightsUpdateConfirmationDialog";

    static props = {
        ...ConfirmationDialog.props,
        destinationFolder: { type: Object },
    };

    get title() {
        return _t("Moving to: %s", this.props.destinationFolder.display_name);
    }
}
