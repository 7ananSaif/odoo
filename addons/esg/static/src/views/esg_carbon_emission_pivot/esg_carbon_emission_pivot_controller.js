import { onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { PivotController } from "@web/views/pivot/pivot_controller";

export class EsgCarbonEmissionPivotController extends PivotController {
    static template = "esg.carbonEmissionPivotView";
    static components = { ...PivotController.components };

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
