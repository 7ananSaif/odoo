import { patch } from '@web/core/utils/patch';
import wSaleUtils from '@website_sale/js/website_sale_utils';
import { WebsiteSale } from '@website_sale/interactions/website_sale';

patch(WebsiteSale.prototype, {
    /**
     * Override of `_updateRootProduct` to add the subscription plan id to the rootProduct for
     * subscription products.
     *
     * @override
     * @private
     * @param {HTMLFormElement} form - The form in which the product is.
     *
     * @returns {void}
     */
    _updateRootProduct(form) {
        super._updateRootProduct(...arguments);
        const selected_plan =
            form.querySelector('input[name="plan_id"]:checked')?.value
            ?? form.querySelector('#add_to_cart')?.dataset.subscriptionPlanId;
        if (selected_plan) {
            const allow_one_time_sale = form.querySelector('.allow_one_time_sale')?.checked;
            const plan_id = allow_one_time_sale ? null : parseInt(selected_plan);
            Object.assign(this.rootProduct, {
                plan_id: plan_id,
                allow_one_time_sale: allow_one_time_sale,
            });
        }
    },

    /**
     * @override
     * @param {MouseEvent} ev
     */
    async onClickAdd(ev) {
        const form = wSaleUtils.getClosestProductForm(ev.currentTarget);
        const inputs = form.querySelectorAll('div.plan_select input[type="radio"]');
        inputs.forEach(input => {
            input.disabled = !input.checked;
        });
        this._handleAddSubscriptionProduct(form);
        return super.onClickAdd(...arguments);
    },

    _handleAddSubscriptionProduct(form) {
        const regularDeliveryCheckbox = form.querySelector('#regular_delivery');
        const oneTimeSaleCheckbox = form.querySelector('#allow_one_time_sale');

        const regularDeliverySection = form.querySelector('.regular-delivery');
        const oneTimeSaleSection = form.querySelector('.one-time-sale');

        const isRegularChecked = regularDeliveryCheckbox?.checked;
        const isOneTimeChecked = oneTimeSaleCheckbox?.checked;

        if (regularDeliverySection) {
            regularDeliverySection.style.display = isRegularChecked ? '' : 'none';
        }

        if (oneTimeSaleSection) {
            oneTimeSaleSection.style.display = (isOneTimeChecked && !isRegularChecked) ? '' : 'none';
        }
    },

    /**
     * @override
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        this._onChangeCombinationSubscription(...arguments);
    },
});
