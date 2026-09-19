import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { SwedenBlackboxError } from "@l10n_se_pos/app/errors/error_handlers";
const { DateTime } = luxon;

patch(PosStore.prototype, {
    useBlackBoxSweden() {
        return !!this.config.iface_sweden_fiscal_data_module;
    },
    disallowLineQuantityChange() {
        const result = super.disallowLineQuantityChange(...arguments);
        return this.useBlackBoxSweden() || result;
    },
    async preSyncAllOrders(orders) {
        if (this.useBlackBoxSweden() && orders.length > 0) {
            for (const order of orders) {
                await this.pushSingleOrder(order);
            }
        }
        return super.preSyncAllOrders(orders);
    },
    async pushSingleOrder(order) {
        if (this.useBlackBoxSweden() && order) {
            if (!order.receipt_type) {
                order.receipt_type = "normal";
                order.sequence_number = await this.getOrderSequenceNumber();
            }
            try {
                order.blackbox_tax_category_a = order.getSpecificTax("A");
                order.blackbox_tax_category_b = order.getSpecificTax("B");
                order.blackbox_tax_category_c = order.getSpecificTax("C");
                order.blackbox_tax_category_d = order.getSpecificTax("D");
                const data = await this.pushOrderToSwedenBlackbox(order);
                if (data.value.error && data.value.error.errorCode != "000000") {
                    throw data.value.error;
                }
                this.setDataForPushOrderFromSwedenBlackBox(order, data);
            } catch (err) {
                order.state = "draft";
                throw new SwedenBlackboxError(err?.status?.message_title ?? err?.status ?? err);
            }
        }
    },
    async pushOrderToSwedenBlackbox(order) {
        const fdm = this.hardwareProxy.deviceControllers.fiscal_data_module;
        const data = {
            date: new DateTime(order.date_order).toFormat("yyyyMMddHHmm"),
            receipt_id: order.sequence_number.toString(),
            pos_id: this.config.id.toString(),
            organisation_number: this.company.company_registry.replace(/\D/g, ""),
            receipt_total: order.displayPrice.toFixed(2).toString().replace(".", ","),
            negative_total:
                order.totalDue < 0
                    ? Math.abs(order.totalDue).toFixed(2).toString().replace(".", ",")
                    : "0,00",
            receipt_type: order.receipt_type,
            vat1: order.blackbox_tax_category_a
                ? "25,00;" + order.blackbox_tax_category_a.toFixed(2).replace(".", ",")
                : " ",
            vat2: order.blackbox_tax_category_b
                ? "12,00;" + order.blackbox_tax_category_b.toFixed(2).replace(".", ",")
                : " ",
            vat3: order.blackbox_tax_category_c
                ? "6,00;" + order.blackbox_tax_category_c.toFixed(2).replace(".", ",")
                : " ",
            vat4: order.blackbox_tax_category_d
                ? "0,00;" + order.blackbox_tax_category_d.toFixed(2).replace(".", ",")
                : " ",
        };

        return new Promise((resolve, reject) => {
            fdm.addListener((data) => (data.status === "ok" ? resolve(data) : reject(data)));
            fdm.action({
                action: "registerReceipt",
                high_level_message: data,
            })
                .then((response) => {
                    if (!response.result) {
                        reject(_t("Blackbox is disconnected"));
                    }
                })
                .catch(reject);
        });
    },
    setDataForPushOrderFromSwedenBlackBox(order, data) {
        order.blackbox_signature = data.signature_control;
        order.blackbox_unit_id = data.unit_id;
    },
    async getOrderSequenceNumber() {
        return await this.data.call("pos.config", "get_order_sequence_number", [this.config.id]);
    },
    async getProfoOrderSequenceNumber() {
        return await this.data.call("pos.config", "get_profo_order_sequence_number", [
            this.config.id,
        ]);
    },
});
