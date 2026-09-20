import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    canEditPayment(order) {
        return this.company.l10n_at_is_fon_authenticated ? false : super.canEditPayment(order);
    },
});
