import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { computeM2OProps, KanbanMany2One } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription, Many2OneField } from "@web/views/fields/many2one/many2one_field";

export class ReferralKanbanMany2OneAvatarUserField extends Component {
    static template = "hr_referral.ReferralKanbanMany2OneAvatarUserField";
    static components = { Avatar, KanbanMany2One };
    static props = { ...Many2OneField.props };

    get m2oProps() {
        return {
            ...computeM2OProps(this.props),
            readonly: false,
        };
    }
}

registry.category("fields").add("kanban.referral_many2one_avatar_user", {
    ...buildM2OFieldDescription(ReferralKanbanMany2OneAvatarUserField),
    additionalClasses: ["o_field_many2one_avatar_kanban", "o_field_many2one_avatar"],
});
