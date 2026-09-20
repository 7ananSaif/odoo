import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";
import { comp, EQ } from "@point_of_sale/app/utils/numbers";

import {
    PrintRecMessage,
    PrintRecItem,
    PrintRecTotal,
    PrintRecRefund,
    PrintRecItemAdjustment,
    PrintRecSubtotalAdjustment,
} from "@l10n_it_pos/app/fiscal_printer/commands";

export class Body extends Component {
    static template = "l10n_it_pos.FiscalDocumentBody";

    static components = {
        PrintRecMessage,
        PrintRecItem,
        PrintRecTotal,
        PrintRecRefund,
        PrintRecItemAdjustment,
        PrintRecSubtotalAdjustment,
    };

    static props = {
        order: {
            type: Object,
            optional: true, // To keep backward compatibility
        },
    };

    setup() {
        this.pos = usePos();
        this.order = this.props.order || this.pos.getOrder();
        this.adjustment = this.order.appliedRounding && {
            description: _t("Rounding"),
            amount: this._itFormatCurrency(Math.abs(this.order.appliedRounding)),
            adjustmentType: this.order.appliedRounding > 0 ? 6 : 1,
        };
    }

    _itFormatCurrency(amount) {
        const decPlaces = this.order.currency_id.decimal_places;
        return formatFloat(amount, {
            thousandsSep: "",
            digits: [0, decPlaces],
        });
    }
    _itFormatQty(qty) {
        const ProductUnit = this.pos.models["decimal.precision"].find(
            (dp) => dp.name === "Product Unit"
        );
        const decimal_places = Math.min(3, ProductUnit.digits);
        return formatFloat(qty, {
            thousandsSep: "",
            digits: [0, decimal_places],
        });
    }
    get isFullDiscounted() {
        return this.order.lines.length > 0 && this.order.currency.isZero(this.order.priceIncl);
    }
    get lines() {
        const calculateDiscountAmount = (line) => {
            const order = line.order_id;
            return order.prices.baseLineByLineUuids[line.uuid].tax_details.discount_amount;
        };

        return this.order.lines.map((line, index) => {
            const order = line.order_id;
            const data = order.prices.baseLineByLineUuids[line.uuid];
            const productName = line.getFullProductName();
            const department = line.tax_ids.map((tax) => tax.tax_group_id.pos_receipt_label)[0];
            const isRefund = line.qty < 0;
            const isReward = line.is_reward_line;
            const quantity = Math.abs(line.qty);
            const totalPrice = isRefund
                ? data.tax_details.total_included
                : data.tax_details.no_discount_total_included;
            const unitPrice = quantity > 0 ? totalPrice / quantity : totalPrice;
            const isGlobalDiscount = this.order.currency.isNegative(unitPrice);
            const unitPriceFormatted = this._itFormatCurrency(
                isGlobalDiscount ? -unitPrice : unitPrice
            );

            return {
                isRefund,
                isReward,
                isGlobalDiscount,
                description: isRefund ? _t("%s (refund)", productName) : productName,
                customer_note: line.getCustomerNote(),
                quantity: this._itFormatQty(quantity),
                // DISCOUNT: Use price before discount because the discounted amount is specified in the printRecItemAdjustment.
                // REFUND: Use the price with tax because there is no adjustment for printRecRefund.
                unitPrice: unitPriceFormatted,
                department,
                index,
                discount: (comp(line.discount, 0, { precision: 1 }) !== EQ || isReward) && {
                    description: isReward
                        ? productName
                        : _t("%s discount (%s)", productName, `${line.discount}%`),
                    amount: this._itFormatCurrency(
                        isReward
                            ? Math.abs(line.price_subtotal_incl)
                            : calculateDiscountAmount(line)
                    ),
                },
            };
        });
    }

    get payments() {
        return this.order.payment_ids
            .filter((payment) => !payment.is_change && payment.amount > 0)
            .map((payment) => ({
                description: _t("Payment in %s", payment.payment_method_id.name),
                payment: this._itFormatCurrency(payment.amount),
                paymentType: payment.payment_method_id.it_payment_code,
                index: payment.payment_method_id.it_payment_index,
                id: payment.id,
            }));
    }
}
