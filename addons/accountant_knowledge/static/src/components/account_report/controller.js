import { patch } from "@web/core/utils/patch";
import { AccountReportController } from "@account_reports/components/account_report/controller";

patch(AccountReportController.prototype, {
    /** @override */
    hasSessionOptions() {
        if (!this.action.context.article_id) {
            return super.hasSessionOptions();
        }
        return true;
    },
    /** @override */
    saveSessionOptions(options) {
        if (!this.action.context.article_id) {
            super.saveSessionOptions(options);
            return;
        }
        this.savedOptions = options;
        const { context } = this.action;
        this.orm.call("knowledge.article", "update_embedded_audit_report_options", [
            context.article_id,
            context.html_element_host_id,
            options,
        ]);
    },
    /** @override */
    sessionOptions() {
        if (!this.action.context.article_id) {
            return super.sessionOptions();
        }
        return this.savedOptions;
    },
});
