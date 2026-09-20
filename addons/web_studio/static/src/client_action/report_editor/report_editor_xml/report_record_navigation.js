import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

import { Pager } from "@web/core/pager/pager";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { useService } from "@web/core/utils/hooks";

export class ReportRecordNavigation extends Component {
    static components = { RecordSelector, Pager };
    static template = "web_studio.ReportEditor.ReportRecordNavigation";
    static props = {
        onWillPrint: { type: Function, optional: true },
    };

    setup() {
        this.reportEditorModel = useState(this.env.reportEditorModel);
        this.action = useService("action");
        this.notification = useService("notification");
    }

    get multiRecordSelectorProps() {
        const currentId = this.reportEditorModel.reportEnv.currentId;
        return {
            resModel: this.reportEditorModel.reportResModel,
            update: (resId) => {
                this.reportEditorModel.loadReportHtml({ resId });
            },
            resId: currentId,
            domain: this.reportEditorModel.getModelDomain(),
            context: { studio: false },
        };
    }

    get pagerProps() {
        const { reportEnv } = this.reportEditorModel;
        const { ids, currentId } = reportEnv;
        return {
            limit: 1,
            offset: ids.indexOf(currentId),
            total: ids.length,
        };
    }

    updatePager({ offset }) {
        const ids = this.reportEditorModel.reportEnv.ids;
        const resId = ids[offset];
        this.reportEditorModel.loadReportHtml({ resId });
    }

    async printPreview() {
        const model = this.reportEditorModel;
        await this.props.onWillPrint?.();
        const recordId = model.reportEnv.currentId || model.reportEnv.ids.find((i) => !!i) || false;
        if (!recordId) {
            this.notification.add(
                _t(
                    "There is no record on which this report can be previewed. Create at least one record to preview the report."
                ),
                {
                    type: "danger",
                    title: _t("Report preview not available"),
                }
            );
            return;
        }

        const action = await rpc("/web_studio/print_report", {
            record_id: recordId,
            report_id: model.editedReportId,
        });
        this.reportEditorModel.renderKey++;
        return this.action.doAction(action, { clearBreadcrumbs: true });
    }
}
