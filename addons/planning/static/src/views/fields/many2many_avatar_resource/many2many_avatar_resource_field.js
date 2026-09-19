import { patch } from "@web/core/utils/patch";
import {
    Many2ManyAvatarResourceField,
    many2ManyAvatarResourceField,
} from "@resource_mail/views/fields/many2many_avatar_resource/many2many_avatar_resource_field";


export const patchM2mResourceFieldPrototype = {
    displayAvatarCard(record) {
        return !this.env.isSmall && this.relation === "resource.resource" &&
            (record.data.resource_type === "user" || record.data.role_ids.currentIds.length > 1);
    },
};

const oldRelatedFields = many2ManyAvatarResourceField.relatedFields;
many2ManyAvatarResourceField.relatedFields = (fieldInfo) => {
    return [
        ...oldRelatedFields(fieldInfo),
        {
            name: "role_ids",
            type: "many2many",
        },
    ];
}
patch(Many2ManyAvatarResourceField.prototype, patchM2mResourceFieldPrototype);
