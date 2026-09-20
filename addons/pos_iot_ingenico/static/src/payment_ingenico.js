import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { PaymentInterfaceIot } from "@pos_iot/app/utils/payment/payment_interface_iot";

export class PaymentIngenico extends PaymentInterfaceIot {
    getPaymentData(uuid) {
        const paymentLine = this.pos.getOrder().getPaymentlineByUuid(uuid);
        return {
            messageType: "Transaction",
            // The last 13 characters of the uuid is a 52-bit integer, fits in the Number data type.
            TransactionID: parseInt(uuid.replace(/-/g, "").slice(19, 32), 16),
            cid: uuid,
            amount: Math.round(paymentLine.amount * 100),
        };
    }

    getCancelData() {
        return {
            messageType: "Cancel",
            reason: "manual",
        };
    }

    getPaymentLineForMessage(order, data) {
        const line = order.getPaymentlineByUuid(data.cid);
        const terminalProxy = line?.payment_method_id.terminal_proxy;
        if (line && terminalProxy) {
            return line;
        }
        return null;
    }

    onTerminalMessageReceived(data, line) {
        this._setCardAndReceipt(data, line);
        if (data.Error) {
            const isCancellation = data.Error === "Canceled";
            if (!isCancellation) {
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("Payment terminal error"),
                    body: _t(data.Error),
                });
            }
            this._resolvePayment?.(false);
            this._resolveCancellation?.(isCancellation);
        } else if (data.Response === "Approved") {
            this._resolvePayment?.(true);
        } else if (["WaitingForCard", "WaitingForPin"].includes(data.Stage)) {
            if (line.payment_status !== "waitingCancel") {
                line.setPaymentStatus("waitingCard");
            }
        }
        if (["Finished"].includes(data.Stage)) {
            this._resolveCancellation?.(true);
        }
    }

    _setCardAndReceipt(data, line) {
        if (data.Ticket) {
            line.setReceiptInfo(data.Ticket);
        }
        if (data.Card) {
            line.card_type = data.Card;
        }
    }
}

register_payment_method("ingenico", PaymentIngenico);
