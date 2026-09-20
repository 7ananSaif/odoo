import { patch } from "@web/core/utils/patch";
import {
    ProductLabelSectionAndNoteField
} from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import {
    SectionAndNoteListRenderer,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";

patch(ProductLabelSectionAndNoteField.prototype, {
    isNote(record = null) {
        record = record || this.props.record;
        const data = super.isNote(record);
        return data || record.data.display_type === "subscription_discount";
    }
});

patch(SectionAndNoteListRenderer.prototype, {
    isSectionOrNote(record=null) {
        record = record || this.record;
        const data = super.isSectionOrNote(record);
        return data || record.data.display_type === "subscription_discount";
    }
});
