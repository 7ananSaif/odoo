import { ProductCatalogKanbanController } from "@product/product_catalog/kanban_controller";
import { useDebounced } from "@web/core/utils/timing";

export class FSMProductCatalogKanbanController extends ProductCatalogKanbanController {
    static template = "web.KanbanView";
    // changing the template to keep the o-kanban-button-new button

    setup() {
        super.setup();
        const { fsm_task_id, active_model } = this.props.context;
        this.taskId = fsm_task_id;
        this.taskResModel = active_model;
        this.backToTaskDebounced = useDebounced(this.backToTask, 500);
    }

    /**
     * @override
     * overriding useless method to prevent wrong orm call
     *
     * **/
    onWillStart() {}

    async backToTask() {
        // Restore the last form view from the breadcrumbs if breadcrumbs are available.
        // If, for some weird reason, the user reloads the page then the breadcrumbs are
        // lost, and we fall back to the form view ourselves.
        if (this.env.config.breadcrumbs.length > 1) {
            await this.actionService.restore();
        } else {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: this.taskResModel,
                views: [[false, "form"]],
                view_mode: "form",
                res_id: this.taskId,
            });
        }
    }
}
