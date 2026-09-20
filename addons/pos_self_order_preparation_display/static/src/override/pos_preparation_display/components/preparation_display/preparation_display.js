import { patch } from "@web/core/utils/patch";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { useService } from "@web/core/utils/hooks";

patch(PrepDisplay.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state.isAlertMenu = false;
    },
    get outOfPaperListFiltered() {
        return this.prepDisplay.data.models["pos.config"].filter((config) => !config.has_paper);
    },
    closeAlertMenu() {
        this.state.isAlertMenu = false;
    },
    openAlertMenu() {
        this.state.isAlertMenu = true;
    },
    async paperNotificationClick(configPaperStatus) {
        configPaperStatus.has_paper = !configPaperStatus.has_paper;
        await this.orm.call(
            "pos.prep.display",
            "change_paper_status",
            [configPaperStatus.id, configPaperStatus.has_paper],
            {}
        );
    },
});
