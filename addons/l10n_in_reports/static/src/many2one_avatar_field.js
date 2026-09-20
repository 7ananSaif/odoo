import { registry } from "@web/core/registry";
import { Many2OneAvatarField } from "@web/views/fields/many2one_avatar/many2one_avatar_field";
import { buildM2OFieldDescription, extractM2OFieldProps } from "@web/views/fields/many2one/many2one_field";

registry.category("fields").add("form.many2one_avatar_no_open", {
    ...buildM2OFieldDescription(Many2OneAvatarField),
    extractProps(staticInfo, dynamicInfo) {
        return {
            ...extractM2OFieldProps(staticInfo, dynamicInfo),
            canOpen: false,
        };
    },
});
