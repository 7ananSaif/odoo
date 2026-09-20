import { patch } from "@web/core/utils/patch";
import { ProjectTaskTemplateDropdown } from "@project/views/components/project_task_template_dropdown";

patch(ProjectTaskTemplateDropdown.prototype, {
    /**
     * @override
     */
    async onWillStart() {
        await super.onWillStart();
        if (
            !this.props.projectId &&
            this.props.context.fsm_mode
        ) {
            this.state.taskTemplates = await this.orm
                .cache({
                    type: "disk",
                    update: "always",
                    callback: (result, hasChanged) => {
                        if (hasChanged) {
                            this.state.taskTemplates = result;
                        }
                    },
                })
                .searchRead(
                    "project.task",
                    [
                        ["is_template", "=", true],
                        ["is_fsm", "=", true],
                    ],
                    ["id", "name"]
                );
        }
    },
});
