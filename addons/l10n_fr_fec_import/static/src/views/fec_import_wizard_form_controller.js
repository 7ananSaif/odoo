import { useChildSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

class FecImportWizardFormController extends FormController {
    setup() {
        super.setup();
        useChildSubEnv({
            fecFileState: { file: {} },
        });
    }
}

registry.category("views").add("fec_import_wizard_form", {
    ...formView,
    Controller: FecImportWizardFormController,
});
