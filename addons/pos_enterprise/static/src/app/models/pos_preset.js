import { PosPreset } from "@point_of_sale/app/models/pos_preset";
import { patch } from "@web/core/utils/patch";

const { DateTime } = luxon;

patch(PosPreset.prototype, {
    get nextSlot() {
        const availabilities = this.uiState.availabilities || {};
        const dates = Object.keys(availabilities).sort();

        for (const date of dates) {
            const slotTimes = Object.keys(availabilities[date]).sort();
            for (const slotTime of slotTimes) {
                const slot = availabilities[date][slotTime];
                if (slot.datetime > DateTime.now()) {
                    return slot;
                }
            }
        }
        return null;
    },
});
