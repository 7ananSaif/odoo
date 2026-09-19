import { patch } from "@web/core/utils/patch";
import { CONSOLE_COLOR, PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this["pos.prep.display"] = [];
    },
    async sendOrderInPreparation(o, opts = {}) {
        const result = await super.sendOrderInPreparation(o, opts);
        if (this.config.preparationDisplayCategories.size > 0) {
            for (const note of Object.values(o.uiState.noteHistory)) {
                for (const n of note) {
                    const line = o.getOrderline(n.lineId);
                    n.qty = line?.getQuantity();
                }
            }
            try {
                const process_order_options = {
                    general_customer_note: o.general_customer_note || "",
                    internal_note: o.internal_note || "",
                    note_history: o.uiState.noteHistory,
                    cancelled: opts.cancelled,
                    fired_course_id: opts.firedCourseId,
                };

                if (opts.cancelled) {
                    await this.data.call("pos.prep.order", "process_order", [
                        o.id,
                        process_order_options,
                    ]);
                } else {
                    await this.syncAllOrders({
                        orders: [o],
                        force: true,
                        context: {
                            preparation: {
                                process_order_options,
                            },
                        },
                    });
                    o.updateSavedQuantity();
                }
            } catch (error) {
                logPosMessage(
                    "Store",
                    "sendOrderInPreparation",
                    "Error while sending order to preparation display",
                    CONSOLE_COLOR,
                    [error]
                );

                // Show error popup only if warningTriggered is false
                if (!this.data.network.warningTriggered) {
                    this.dialog.add(AlertDialog, {
                        title: _t("Send failed"),
                        body: _t("Failed in sending the changes to preparation display"),
                    });
                }
            }
            o.uiState.noteHistory = {};
        }

        return result;
    },
});
