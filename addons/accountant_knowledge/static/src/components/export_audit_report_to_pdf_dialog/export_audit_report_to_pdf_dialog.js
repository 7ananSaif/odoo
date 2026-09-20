import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class ExportAuditReportToPDFDialog extends Component {
    static template = "accountant_knowledge.ExportAuditReportToPDFDialog";
    static components = { Dialog };
    static props = {
        record: Object,
        close: Function,
    };

    setup() {
        this.action = useService("action");
        this.state = useState({
            includePdfFiles: true,
            includeChildArticles: true,
        });
    }

    async exportAuditReportToPDF() {
        this.props.close();
        await this.action.doAction({
            type: "ir.actions.act_url",
            target: "download",
            url: `/knowledge_accountant/article/${this.props.record.resId}/audit_report?include_pdf_files=${this.state.includePdfFiles}&include_child_articles=${this.state.includeChildArticles}`,
        });
    }
}
