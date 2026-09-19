/* global posmodel */

import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import { inLeftSide } from "@point_of_sale/../tests/pos/tours/utils/common";

class PaymentTerminalDummy {
    iotId = 1;
    identifier = "scale_1";
}

class IotHttpServiceDummy {
    action(iotBoxId, deviceIdentifier, data, onSuccess) {
        if (data.messageType === "Transaction") {
            if (this.transaction) {
                throw "Another transaction is still running";
            }
            this.transaction = true;
            this.cid = data.cid;
            onSuccess({
                status: "success",
                result: {
                    Stage: "WaitingForCard",
                    cid: this.cid,
                },
            });
        } else if (data.messageType === "Cancel") {
            clearTimeout(this.txApprovedTimeout);
            this.transaction = false;
            onSuccess({
                status: "success",
                result: {
                    Error: "Canceled",
                    cid: this.cid,
                },
            });
        }
        return Promise.resolve();
    }
    onMessage(_iotBoxId, _deviceIdentifier, onSuccess) {
        this.txApprovedTimeout = setTimeout(() => {
            onSuccess({
                status: "success",
                result: {
                    Response: "Approved",
                    cid: this.cid,
                },
            });
            this.transaction = false;
        }, 1000);
    }
}

registry.category("web_tour.tours").add("payment_terminals_tour", {
    steps: () =>
        [
            stepUtils.showAppsMenuItem(),
            {
                content: "Select PoS app",
                trigger: '.o_app[data-menu-xmlid="point_of_sale.menu_point_root"]',
                run: "click",
            },
            {
                content: "Start session",
                trigger: ".o_pos_kanban button.oe_kanban_action",
                run: "click",
                expectUnloadPage: true,
            },
            // PART 1: Pay exactly the price of order. Should automatically go to receipt screen.
            {
                content: "confirm dialog",
                trigger: ".modal .modal-footer .btn-primary:contains(Open Register)",
                run: "click",
            },
            {
                content: "Waiting for loading to finish",
                trigger: ".pos .pos-content",
                run: function () {
                    posmodel.iotHttp = new IotHttpServiceDummy();
                    posmodel.models["pos.payment.method"].forEach(function (payment_method) {
                        if (payment_method.terminal_proxy) {
                            payment_method.terminal_proxy = new PaymentTerminalDummy();
                        }
                    });
                },
            },
            {
                content: "Buy a Test Product",
                trigger: '.product-list .product-name:contains("Test Product")',
                run: "click",
            },
            ...inLeftSide(Order.hasLine({ productName: "Test Product" })),
            {
                content: "Go to payment screen",
                trigger: ".button.pay-order-button",
                run: "click",
            },
            {
                content: "There should be no payment line",
                trigger: ".paymentlines-empty",
            },
            {
                content: "Pay with payment terminal",
                trigger: '.paymentmethod:contains("Terminal")',
                run: "click",
            },
            {
                content: "Cancel payment",
                trigger: ".button.send_payment_cancel",
                run: "click",
            },
            ...PaymentScreen.clickPaymentlineDelButton("Terminal", "10.00"),
            {
                trigger: ".paymentlines-empty",
            },
            ...PaymentScreen.enterPaymentLineAmount("Terminal", "5", true, { remainingIs: "5.00" }),
            {
                trigger: ".button.send_payment_request.highlight",
                run: "click",
            },
            {
                trigger: ".electronic_status:contains('Successful')",
            },
            ...PaymentScreen.clickPaymentMethod("Cash"),
            ...PaymentScreen.clickNumpad("5"),
            ...PaymentScreen.validateButtonIsHighlighted(),
            ...PaymentScreen.clickValidate(),
            {
                content: "Immediately at the receipt screen.",
                trigger: '.receipt-screen .button.next.highlight:contains("New Order")',
            },
        ].flat(),
});
