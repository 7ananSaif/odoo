import { onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { GraphController } from "@web/views/graph/graph_controller";

export class EsgCarbonEmissionGraphController extends GraphController {
    static template = "esg.carbonEmissionGraphView";

    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.title = _t("Carbon Analytics");

        onWillStart(async () => {
            this.accountantInstalled =
                (await this.orm.searchCount("ir.module.module", [
                    ["name", "=", "accountant"],
                    ["state", "=", "installed"],
                ])) > 0;
        });
    }
}
