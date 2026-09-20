import { registry } from "@web/core/registry"
import { ForecastGanttModel } from "./forecast_gantt_model";
import { planningGanttView } from "@planning/views/planning_gantt/planning_gantt_view";

const forecastGanttView = {
    ...planningGanttView,
    Model: ForecastGanttModel,
};

registry.category("views").add("forecast_gantt", forecastGanttView);
