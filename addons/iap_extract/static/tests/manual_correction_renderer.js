import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormRenderer } from "@web/views/form/form_renderer";

import { ExtractMixinFormRenderer } from '@iap_extract/components/manual_correction/form_renderer';

export class ManualCorrectionFormRenderer extends ExtractMixinFormRenderer(FormRenderer) {
    setup() {
        super.setup();

        this.recordModel = 'iap_extract.manual.correction';
    }

    createBoxLayerApp(props) {
        // Mock the width and height to match the size of the test attachment
        Object.defineProperty(props.pageLayer, 'clientWidth', {value: 210});
        Object.defineProperty(props.pageLayer, 'clientHeight', {value: 297});
        return super.createBoxLayerApp(...arguments);
    }
};


export const ManualCorrectionFormViewExtract = {
    ...formView,
    Renderer: ManualCorrectionFormRenderer,
};

registry.category("views").add("manual_correction_form", ManualCorrectionFormViewExtract);
