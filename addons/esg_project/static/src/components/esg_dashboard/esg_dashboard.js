import { EsgDashboard } from "@esg/components/esg_dashboard/esg_dashboard";
import { EsgProjectInitiativesBox } from "@esg_project/components/esg_dashboard/esg_project_initiatives_box/esg_project_initiatives_box";
import { patch } from "@web/core/utils/patch";

patch(EsgDashboard, {
    components: {
        ...EsgDashboard.components,
        EsgProjectInitiativesBox,
    },
});

patch(EsgDashboard.prototype, {
    get dashboardComponents() {
        return {
            ...super.dashboardComponents,
            3: {
                component: EsgProjectInitiativesBox,
                props: {
                    data: this.data.initiatives_box,
                },
            },
        };
    },
});
