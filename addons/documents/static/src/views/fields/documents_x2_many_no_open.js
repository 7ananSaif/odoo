import { registry } from "@web/core/registry";
import { x2ManyField, X2ManyField } from "@web/views/fields/x2many/x2many_field";

class DocumentsX2ManyFieldNoOpen extends X2ManyField {
    setup() {
        super.setup(...arguments);
        this.canOpenRecord = false;
    }
}

export const documentsX2ManyFieldNoOpen = {
    ...x2ManyField,
    component: DocumentsX2ManyFieldNoOpen,
};

registry.category("fields").add("documents_x2many_no_open", documentsX2ManyFieldNoOpen);
