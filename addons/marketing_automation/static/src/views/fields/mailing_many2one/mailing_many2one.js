import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

class MailingMany2OneField extends Component {
    static template = "marketing_automation.MailingMany2OneField";
    static components = { Many2One };
    static props = { ...Many2OneField.props };

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get m2oProps() {
        return {
            ...computeM2OProps(this.props),
            openRecordAction: () => this.openRecordInAction(),
            createAction: (params) => this.createAction(params),
        };
    }

    openAction(resId, context) {
        this.action.doAction("marketing_automation.mailing_mailing_action_view_form", {
            props: { resId },
            additionalContext: context,
        });
    }

    async createAction({ context }) {
        if (!(await this.props.record.save())) {
            return;
        }
        const actionContext = {
            ...context,
            ...this.props.context,
            default_marketing_activity_ids: [this.props.record.resId],
        };
        this.openAction(false, actionContext);
    }

    async openRecordInAction() {
        if (!(await this.props.record.save())) {
            return;
        }
        const { value, openActionContext } = this.m2oProps;
        this.openAction(value?.id || false, openActionContext());
    }
}

registry.category("fields").add("mailing_many2one", {
    ...buildM2OFieldDescription(MailingMany2OneField),
});
