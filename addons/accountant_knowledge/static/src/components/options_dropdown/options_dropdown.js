import { patch } from "@web/core/utils/patch";
import { OptionsDropdown } from "@knowledge/components/options_dropdown/options_dropdown";
import { ExportAuditReportToPDFDialog } from "@accountant_knowledge/components/export_audit_report_to_pdf_dialog/export_audit_report_to_pdf_dialog";

patch(OptionsDropdown.prototype, {
    exportAuditReportToPDF() {
        this.dialog.add(ExportAuditReportToPDFDialog, {
            record: this.props.record,
        });
    },
});
