import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

export const DocumentsWithAccessX2ManyField = {
    component: X2ManyField,
    displayName: _t("Documents With Access Rights"),
    supportedTypes: ["many2many", "one2many"],
    relatedFields: () => [
        { name: "display_name", type: "char" },
        { name: "access_internal", type: "char" },
        { name: "access_via_link", type: "char" },
        { name: "is_access_via_link_hidden", type: "boolean" },
    ],
};

registry.category("fields").add("documents_with_access_2many", DocumentsWithAccessX2ManyField);
