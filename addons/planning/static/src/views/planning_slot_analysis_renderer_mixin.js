export const PlanningSlotAnalysisRendererMixin = (T) => class PlanningSlotAnalysisRendererMixin extends T {
    openView(domain, views, context) {
        this.actionService.doAction({
            context,
            domain: [...(domain || []), ["start_datetime", "!=", false]],
            name: "Planning",
            res_model: "planning.slot",
            target: "current",
            type: "ir.actions.act_window",
            views,
        }, {
            viewType: "list",
        });
    }
}
