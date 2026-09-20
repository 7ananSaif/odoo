import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class DocumentsMany2OneAvatarField extends Component {
    static template = "documents.DocumentsMany2OneAvatarField";
    static props = { ...standardFieldProps };
    static components = {
        Avatar,
    };

    get user() {
        return user;
    }
}

export const documentsMany2OneAvatarField = {
    component: DocumentsMany2OneAvatarField,
    supportedTypes: ["many2one"], // res.partner or res.users
    relatedFields: [
        { name: "active", type: "boolean" },
        { name: "email", type: "char" },
        { name: "name", type: "char" },
    ],
};

registry.category("fields").add("documents_many2one_avatar", documentsMany2OneAvatarField);
