import { registry } from "@web/core/registry";
import {
    KanbanMany2ManyAvatarUserTagsList,
    KanbanMany2ManyTagsAvatarUserField,
    kanbanMany2ManyTagsAvatarUserField,
} from "@mail/views/web/fields/many2many_avatar_user_field/many2many_avatar_user_field";


export class Many2ManyAvatarUserApproverTagsList extends KanbanMany2ManyAvatarUserTagsList {
    static template = "account_reports.KanbanMany2ManyAvatarUserTagsList";
}


export class Many2ManyAvatarUserApprover extends KanbanMany2ManyTagsAvatarUserField {
    static components = {
        ...KanbanMany2ManyTagsAvatarUserField.components,
        TagsList: Many2ManyAvatarUserApproverTagsList,
    }
}

export const many2ManyAvatarUserApprover = {
    ...kanbanMany2ManyTagsAvatarUserField,
    component: Many2ManyAvatarUserApprover,
};

registry.category("fields").add("kanban.many2many_avatar_user_approver", many2ManyAvatarUserApprover);
