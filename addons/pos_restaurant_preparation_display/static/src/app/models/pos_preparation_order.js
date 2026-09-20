import { deserializeDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";
export class PosPrepOrder extends Base {
    static pythonModel = "pos.prep.order";

    getDurationSinceFireDate() {
        const timeDiff = (
            (luxon.DateTime.now().ts - deserializeDateTime(this.course.fired_date).ts) /
            1000
        ).toFixed(0);
        return Math.round(timeDiff / 60);
    }
}

registry.category("pos_available_models").add(PosPrepOrder.pythonModel, PosPrepOrder);
