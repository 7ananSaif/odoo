import { registry } from "@web/core/registry";
import { projectProjectListView } from "@project/views/project_project_list/project_project_list_view";
import { DatabasesProjectListRenderer } from "./databases_project_list_renderer";

export const databasesProjectListView = {
    ...projectProjectListView,
    Renderer: DatabasesProjectListRenderer,
};

registry.category("views").add("databases_project_list", databasesProjectListView);
