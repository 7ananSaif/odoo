import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { FileUploader } from "@web/views/fields/file_handler";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

class FecImportUploader extends Component {
    static template = "l10n_fr_fec_import.FecImportUploader";
    static props = standardWidgetProps;
    static components = { FileUploader };

    setup() {
        this.fecFileState = useState(this.env.fecFileState);
    }

    onFileChanged(file) {
        this.fecFileState.file = file;
    }
}

registry.category("view_widgets").add("fec_import_uploader", { component: FecImportUploader });
