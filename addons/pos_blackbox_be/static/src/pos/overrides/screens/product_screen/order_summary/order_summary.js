import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(OrderSummary.prototype, {
    _setValue(val) {
        if (this.currentOrder.getSelectedOrderline()) {
            // Do not allow to sent line with a quantity of 5 numbers.
            if (this.pos.useBlackBoxBe() && this.pos.numpadMode === "quantity" && val > 9999) {
                val = 9999;
            }
        }
        super._setValue(val);
    },
    async updateQuantityNumber(newQuantity) {
        if (!this.pos.useBlackBoxBe()) {
            return await super.updateQuantityNumber(newQuantity);
        }
        if (newQuantity === null) {
            return false;
        }
        if (newQuantity > 9999) {
            newQuantity = 9999;
        }
        if (this.pos.getOrder().preset_id?.is_return) {
            newQuantity = -Math.abs(newQuantity);
        }
        const order = this.pos.getOrder();
        const selectedLine = order.getSelectedOrderline();
        // if newQuantity is the same sign as old quantity, then the product of the two will be
        // a positive number and thus will not change the sign of the selectedLine.get_display_price()
        const newPriceSign = Math.sign(selectedLine.currencyDisplayPriceUnit * newQuantity);
        if (
            order.lines.some(
                (l) => l.uuid != selectedLine.uuid && l.prices.total_included * newPriceSign < 0
            )
        ) {
            this.dialog.add(AlertDialog, {
                title: _t("Refund and Sales not allowed"),
                body: _t(
                    "It is not allowed to mix refunds and sales (positive lines and negative lines)."
                ),
            });
            return false;
        }
        return await super.updateQuantityNumber(newQuantity);
    },
    async handleDecreaseUnsavedLine(newQuantity) {
        if (!this.pos.useBlackBoxBe()) {
            return await super.handleDecreaseUnsavedLine(newQuantity);
        }
        await this.pos.pushCorrection(this.currentOrder, [
            this.currentOrder.getSelectedOrderline(),
        ]);
        const decreasedQuantity = await super.handleDecreaseUnsavedLine(newQuantity);
        await this.pos.pushProFormaOrderLog(this.currentOrder);
        return decreasedQuantity;
    },
    async handleDecreaseLine(newQuantity) {
        if (!this.pos.useBlackBoxBe()) {
            return await super.handleDecreaseLine(newQuantity);
        }
        await this.pos.pushCorrection(this.currentOrder, [
            this.currentOrder.getSelectedOrderline(),
        ]);
        const oldTotal = this.currentOrder.priceIncl;
        const decreasedQuantity = await super.handleDecreaseLine(newQuantity);
        await this.pos.increaseCorrectionCounter(oldTotal - this.currentOrder.priceIncl);
        await this.pos.pushProFormaOrderLog(this.currentOrder);
        return decreasedQuantity;
    },
    getNewLine() {
        if (!this.pos.useBlackBoxBe()) {
            return super.getNewLine();
        }
        return this.currentOrder.getSelectedOrderline();
    },
    async setLinePrice(line, price) {
        if (!this.pos.useBlackBoxBe()) {
            return await super.setLinePrice(line, price);
        }
        const oldPrice = line.unitPrices.no_discount_total_included;
        if (price > oldPrice) {
            return;
        }
        const discount = ((oldPrice - price) / oldPrice) * 100;
        line.setDiscount(discount);
    },
});
