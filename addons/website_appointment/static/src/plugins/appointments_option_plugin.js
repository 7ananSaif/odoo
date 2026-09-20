import { DYNAMIC_SNIPPET } from "@website/builder/plugins/options/dynamic_snippet_option_plugin";
import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { registry } from "@web/core/registry";
import { AppointmentsOption } from "./appointments_option";

class AppointmentsOptionPlugin extends Plugin {
    static id = "AppointmentsOption";
    static dependencies = ["dynamicSnippetOption"];
    static shared = [
        "getModelNameFilter",
    ];
    modelNameFilter = "appointment.type";
    resources = {
        builder_options: withSequence(DYNAMIC_SNIPPET, AppointmentsOption),
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
    };
    getModelNameFilter() {
        return this.modelNameFilter;
    }
    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(AppointmentsOption.selector)) {
            await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }
}

registry
    .category("website-plugins")
    .add(AppointmentsOptionPlugin.id, AppointmentsOptionPlugin);
