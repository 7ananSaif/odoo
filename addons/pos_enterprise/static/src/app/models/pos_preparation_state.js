import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";
import { computeDurationSinceDate } from "@pos_enterprise/app/utils/utils";

const { DateTime } = luxon;
export class PosPreparationState extends Base {
    static pythonModel = "pos.prep.state";

    setup(vals) {
        super.setup(vals);
        this.timeToShow = 0;

        const orderPresetTime = this.prep_line_id.prep_order_id.pos_order_id.preset_time;
        if (orderPresetTime) {
            const preset = this.prep_line_id.prep_order_id.pos_order_id.preset_id;
            if (preset.nextSlot?.datetime.ts < orderPresetTime.ts) {
                this.timeToShow =
                    orderPresetTime.minus({ minutes: preset.interval_time }) - DateTime.now();
                setTimeout(() => {
                    this.timeToShow = 0;
                }, this.timeToShow);
            }
        }
    }

    get product() {
        return this.prep_line_id.product_id;
    }

    get categories() {
        return this.product.pos_categ_ids;
    }

    get isCancelled() {
        return this.prep_line_id.quantity - this.prep_line_id.cancelled === 0;
    }

    computeDuration() {
        return computeDurationSinceDate(this.write_date);
    }

    isStageDone(stage_id, todo = false) {
        return this.stage_id.id === stage_id && this.todo === todo;
    }
}

registry.category("pos_available_models").add(PosPreparationState.pythonModel, PosPreparationState);
