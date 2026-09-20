import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";
import { IntegerField } from "@web/views/fields/integer/integer_field";

export class DocumentSizeIntegerField extends IntegerField {
    get formattedValue() {
        if (!this.value) {
            return "";
        }
        return `${formatFloat(this.value, { humanReadable: true })}B`;
    }
}

const documentSizeIntegerField = {
    component: DocumentSizeIntegerField,
    displayName: _t("DocumentSizeIntegerField"),
    supportedTypes: ["integer"],
};

registry.category("fields").add("document_size", documentSizeIntegerField);
