import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useImportModel } from "@base_import/import_model";
import { useFECParser } from "@l10n_fr_fec_import/hooks/fec_parser_hook";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ImportDataProgress } from "@base_import/import_data_progress/import_data_progress";

class FecImportButton extends Component {
    static template = "l10n_fr_fec_import.FecImportButton";
    static props = standardWidgetProps;

    setup() {
        this.fecFileState = useState(this.env.fecFileState);
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.importState = useState({
            totalChunks: 0,
            importProgress: {
                value: 0,
                step: 1,
            },
            interrupted: false,
        });
        this.importModel = useImportModel({ env: this.env });
        this.fecParser = useFECParser();
    }

    block() {
        const blockComponent = {
            class: ImportDataProgress,
            props: {
                stopImport: () => (this.importState.interrupted = true),
                totalSteps: this.importState.totalChunks,
                importProgress: this.importState.importProgress,
            },
        };
        this.importModel.block(_t("Importing FEC"), blockComponent);
    }

    async openImportSummary() {
        const importSummaryAction = await this.orm.call(
            "account.fec.import.wizard",
            "import_summary_action",
            [[this.props.record.resId]]
        );
        this.action.doAction(importSummaryAction);
        this.importModel.unblock();
    }

    async sendChunk(header, rows) {
        try {
            await this.orm.call(
                "account.fec.import.wizard",
                "process_chunk",
                [[this.props.record.resId]],
                {
                    header,
                    rows,
                }
            );
            this.importState.importProgress.step++;
            this.importState.importProgress.value = Math.round((this.importState.importProgress.step / (this.importState.totalChunks || 1)) * 100);
        } catch (error) {
            await this.openImportSummary();
            throw error;
        }
    }

    async startImportProcess() {
        // The wizard is saved first to have correct values of
        // fields document_prefix and duplicate_documents_handling
        await this.props.record.save();
        let parsedFile;
        try {
            parsedFile = this.fecParser.parse(this.fecFileState.file);
            this.importState.totalChunks = parsedFile.chunks.length;
        } catch (error) {
            this.notification.add(_t("\nPlease upload a new valid file"), { type: "warning" });
            this.notification.add(error.message, { type: "danger" });
            return;
        }

        this.block();
        for (const chunk of parsedFile.chunks) {
            await this.sendChunk(parsedFile.header, chunk);
            if (this.importState.interrupted) {
                break;
            }
        }
        await this.openImportSummary();
    }
}

registry.category("view_widgets").add("fec_import_button", { component: FecImportButton });
