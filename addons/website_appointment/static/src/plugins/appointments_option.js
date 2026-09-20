import { BaseOptionComponent } from "@html_builder/core/utils";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";

export class AppointmentsOption extends BaseOptionComponent {
    static template = "website_appointment.AppointmentsOption";
    static dependencies = ["AppointmentsOption"];
    static selector = ".s_appointments";
    setup() {
        super.setup();
        const { getModelNameFilter } = this.dependencies.AppointmentsOption;
        this.dynamicOptionParams = useDynamicSnippetOption(getModelNameFilter());
    }
}
