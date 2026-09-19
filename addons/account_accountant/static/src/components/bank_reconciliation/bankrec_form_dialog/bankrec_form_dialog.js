import { FormController } from "@web/views/form/form_controller";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { formView } from "@web/views/form/form_view";
import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

export class BankRecFormDialog extends FormViewDialog {
    setup() {
        super.setup();
        Object.assign(this.viewProps, {
            buttonTemplate: 'accountant.BankRecFormDialog.buttons',
        });
    }
}

export class BankRecEditLineFormController extends FormController {
    setup() {
        super.setup();
        this.isReviewed = this.props.context.is_reviewed;
        onWillStart(async () => {
            this.userCanReview = await user.hasGroup("account.group_account_user");
        })
    }

    async toReviewButtonClicked (params = {}) {
        await this.orm.call("account.move", "set_moves_checked", [
            this.model.root.data.move_id.id,
            false,
        ]);
        return this.saveButtonClicked(params);
    }
}

export const bankRecEditLineFormController = {
    ...formView,
    Controller: BankRecEditLineFormController,
};

registry.category("views").add("bankrec_edit_line", bankRecEditLineFormController);
