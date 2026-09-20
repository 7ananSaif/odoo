import { EsgDashboard } from "@esg/components/esg_dashboard/esg_dashboard";
import { EsgHrSexParityBox } from "@esg_hr/components/esg_dashboard/esg_hr_sex_parity_box/esg_hr_sex_parity_box";
import { patch } from "@web/core/utils/patch";

patch(EsgDashboard, {
    components: {
        ...EsgDashboard.components,
        EsgHrSexParityBox,
    },
});

patch(EsgDashboard.prototype, {
    get dashboardComponents() {
        return {
            ...super.dashboardComponents,
            4: {
                component: EsgHrSexParityBox,
                props: {
                    data: this.data.sex_parity_box,
                },
            },
        };
    },
});
