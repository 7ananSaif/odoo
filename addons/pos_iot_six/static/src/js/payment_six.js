import { _t } from "@web/core/l10n/translation";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { PaymentInterfaceIot } from "@pos_iot/app/utils/payment/payment_interface_iot";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class PaymentSix extends PaymentInterfaceIot {
    getPaymentData(uuid) {
        const paymentLine = this.pos.getOrder().getPaymentlineByUuid(uuid);
        return {
            messageType: "Transaction",
            transactionType: paymentLine.amount >= 0 ? "Payment" : "Refund",
            amount: Math.abs(Math.round(paymentLine.amount * 100)),
            currency: this.pos.currency.name,
            cid: uuid,
            posId: this.pos.session.id,
            userId: this.pos.session.user_id.id,
        };
    }

    getCancelData(uuid) {
        return {
            messageType: "Cancel",
            cid: uuid,
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
        if (data.Stage === "Cancel") {
            // Result of a cancel request
            if (data.Error) {
                this._resolveCancellation?.(false);
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("Transaction could not be cancelled"),
                    body: data.Error,
                });
            } else {
                this._resolveCancellation?.(true);
                this._resolvePayment?.(false);
            }
        } else if (data.Disconnected) {
            // Terminal disconnected
            line.setPaymentStatus("force_done");
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Terminal Disconnected"),
                body: _t(
                    "Please check the network connection and then check the status of the last transaction manually."
                ),
            });
        } else if (line.payment_status !== "retry") {
            // Result of a transaction
            if (data.Error) {
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("Payment terminal error"),
                    body: _t(data.Error),
                });
                this._resolvePayment?.(false);
            } else if (data.Response === "Approved") {
                this._resolvePayment?.(true);
            } else if (["WaitingForCard", "WaitingForPin"].includes(data.Stage)) {
                line.setPaymentStatus("waitingCard");
            }
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

    _onBalanceComplete(data) {
        if (data.Error || !data.Ticket) {
            const error_msg =
                data.Error && data.Error != ""
                    ? data.Error
                    : _t("Failed to get balance report from the terminal. Please retry.");
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Six balance report error"),
                body: error_msg,
            });
            return;
        }
        const wrapper = document.createElement("div");
        wrapper.innerHTML = `<div class='pos-receipt'>
                <div class='pos-payment-terminal-receipt' style='font-size: 32px;'>
                    ${data.Ticket.replace(/\n/g, "<br>")}
                </div>
            </div>`;
        const element = wrapper.firstElementChild;
        this.pos.hardwareProxy.printer.printReceipt(element);
    }

    async sendBalance() {
        var self = this;
        if (!self.terminal) {
            this._showErrorConfig();
            return false;
        }
        const printer = this.pos.hardwareProxy.printer;
        if (!printer) {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("No printer configured"),
                body: _t(
                    "You must select a printer in your POS config to print Six balance report"
                ),
            });
            return false;
        }
        const data = {
            messageType: "Balance",
            posId: self.pos.session.id,
            userId: self.pos.session.user_id.id,
        };

        return this.pos.iotHttp.action(
            this.terminal.iotId,
            this.terminal.identifier,
            data,
            (e) => this._onBalanceComplete(e.result),
            (e) => this._onBalanceComplete(e)
        );
    }
}

register_payment_method("six_iot", PaymentSix);
