import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { renderToMarkup } from '@web/core/utils/render';
import { patchDynamicContent } from '@web/public/utils';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            'input[name="o_payment_automate_payments_new_token"]': {
                't-on-change': this.onChangeAutomatePaymentsCheckbox.bind(this)
            },
        });
    },
    /**
     * Replace the base token deletion confirmation dialog to prevent token deletion if a linked
     * subscription is active.
     *
     * @override method from @payment/interactions/payment_form
     * @private
     * @param {number} tokenId - The id of the token whose deletion was requested.
     * @param {object} linkedRecordsInfo - The data relative to the documents linked to the token.
     * @return {void}
     */
    _challengeTokenDeletion(tokenId, linkedRecordsInfo) {
        if (linkedRecordsInfo.every(linkedRecordInfo => !linkedRecordInfo['active_subscription'])) {
            super._challengeTokenDeletion(...arguments);
            return;
        }

        const body = renderToMarkup('sale_subscription.deleteTokenDialog', { linkedRecordsInfo });
        this.services.dialog.add(ConfirmationDialog, {
            title: _t("Warning!"),
            body,
            cancel: () => {},
        });
    },

    /**
     * Override of payment method to update the paymentContext.transactionRoute depending
     * on the order we are paying.
     * For subscription invoices, when the customer wants to save the token on the order,
     * we update the transaction route on the fly.
     *
     * @param {Event} ev
     * @return {void}
     */
    async submitForm(ev) {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(checkedRadio);

        // Fetch the `autoPaymentCheckboxNewToken` of the current payment method.
        const autoPaymentCheckboxNewToken = inlineForm?.querySelector(
            'input[name="o_payment_automate_payments_new_token"]'
        );
        // Fetch the `autoPaymentCheckboxSavedToken` of the current token.
        const autoPaymentCheckboxSavedToken = inlineForm?.querySelector(
            `input[name="o_payment_automate_payments_saved_token"]`
        );

        if ((autoPaymentCheckboxNewToken?.checked || autoPaymentCheckboxSavedToken?.checked) &&
            this.paymentContext.txRouteSubscription) {
            // TODO Should be replaced with an override of the account_payment controller to extend
            // it with subscription logic.
            this.paymentContext.transactionRoute = this.paymentContext.txRouteSubscription;
        }
        return await super.submitForm(...arguments);
    },

    /**
     * Automatically check `Save my payment details` checkbox after clicking in the `Automate payments` option.
     *
     * @return {void}
     */
    onChangeAutomatePaymentsCheckbox: function (ev) {
        // Fetch the `savePaymentMethodCheckbox` of the current payment method.
        const tokenizeContainer = ev.currentTarget.closest(
            'div[name="o_payment_tokenize_container"]'
        );
        const savePaymentMethodCheckbox = tokenizeContainer.querySelector(
            'input[name="o_payment_tokenize_checkbox"]'
        );
        savePaymentMethodCheckbox.checked = ev.currentTarget.checked;
        savePaymentMethodCheckbox.disabled = ev.currentTarget.checked;
        // Dispatch a fake event to update the payment form dependencies.
        savePaymentMethodCheckbox.dispatchEvent(new Event('input'));
    },

    /**
     * Prepare the params for the RPC to the transaction route.
     *
     * @private
     * @param {number} providerId - The id of the provider handling the transaction.
     * @returns {object} - The transaction route params.
     */
    _prepareTransactionRouteParams(providerId) {
        const transactionRouteParams = super._prepareTransactionRouteParams(...arguments);
        if (this.paymentContext.subscriptionAnticipate) {
            transactionRouteParams['subscription_anticipate'] = this.paymentContext.subscriptionAnticipate;
        }
        return transactionRouteParams;
    },

});
