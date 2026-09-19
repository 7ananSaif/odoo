import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";

import { useReportEditorModel } from "@web_studio/client_action/report_editor/report_editor_model";
import { ReportEditorWysiwyg } from "@web_studio/client_action/report_editor/report_editor_wysiwyg/report_editor_wysiwyg";
import { ReportEditorXml } from "@web_studio/client_action/report_editor/report_editor_xml/report_editor_xml";

import { getCssFromPaperFormat } from "./utils";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class ReportEditor extends Component {
    static template = "web_studio.ReportEditor";
    static components = { ReportEditorWysiwyg, ReportEditorXml };
    static props = { ...standardActionServiceProps };

    setup() {
        this.reportEditorModel = useReportEditorModel();
    }

    get paperFormatStyle() {
        const {
            margin_top,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
            header_spacing,
        } = this.reportEditorModel.paperFormat;
        const marginTop = Math.max(0, (margin_top || 0) - (header_spacing || 0));
        return getCssFromPaperFormat({
            margin_top: marginTop,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
        });
    }
}
registry.category("actions").add("web_studio.report_editor", ReportEditor);

class ReportsTab extends Component {
    static template = "web_studio.ReportEditor.ReportsTab";
    static props = {
        tab: Object,
        editedAction: Object,
        openTab: Function,
    };

    setup() {
        this.studio = useService("studio");
        onWillStart(() => this.updateFromModel(this.props.editedAction.res_model));
        onWillUpdateProps((next) => this.updateFromModel(next.editedAction.res_model));
    }

    onClick() {
        if (this.isDisabled) {
            return;
        }
        this.props.openTab(this.props.tab.id);
    }

    get isDisabled() {
        return !this.modelInfo.record_ids.length;
    }

    get tooltip() {
        if (!this.isDisabled) {
            return false;
        }
        return _t("You cannot edit a report while there is no %(model_name)s (%(model)s)", {
            model_name: this.modelInfo.name,
            model: this.modelInfo.model,
        });
    }

    async updateFromModel(resModel) {
        this.modelInfo = await this.studio.IrModelInfo.read(resModel);
    }
}

registry
    .category("web_studio.editor_tabs")
    .add("reports", { name: _t("Reports"), Component: ReportsTab }, { sequence: 15 });
