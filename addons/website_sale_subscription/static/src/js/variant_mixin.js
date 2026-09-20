import { renderToElement } from "@web/core/utils/render";
import VariantMixin from '@website_sale/js/variant_mixin';

/**
 * Update the renting text when the combination change.
 *
 * @param {Event} ev
 * @param {Element} parent
 * @param {object} combination
 */
VariantMixin._onChangeCombinationSubscription = function (ev, parent, combination) {
    if (!combination.is_subscription) {
        return;
    }
    const unit = parent.querySelector(".o_subscription_unit");
    const price = parent.querySelector(".o_subscription_price") || parent.querySelector(".product_price h5");
    const addToCartButton = document.querySelector('#add_to_cart');
    const pricingSelect =
        parent.querySelector(".js_main_product h5:has(.o_subscription_price)") ||
        parent.querySelector(".js_main_product .plan_select");

    if (pricingSelect) {
        const disabledPlanIds = Array.from(
            pricingSelect.querySelectorAll("input[type='radio']:disabled"),
            radioButton => +radioButton.value
        );
        if (disabledPlanIds.length) {
            combination.pricings.forEach(pricing => {
                if (disabledPlanIds.includes(pricing.plan_id)) pricing.can_be_added = false;
            });
        }
        pricingSelect.replaceWith(
            renderToElement("website_sale_subscription.SubscriptionPricingTableSelect", {
                combination_info: combination,
            })
        );
    } else {
        // we don't find the element in the dom which means there was no pricings in the previous combination so there is no `Radio buttons` or `h5` elements to replace then we append one.
        const nodeToAppend = parent.querySelector(".js_main_product div div");
        nodeToAppend.append(
            renderToElement("website_sale_subscription.SubscriptionPricingTableSelect", {
                combination_info: combination,
            })
        );
    }
    if (combination.allow_one_time_sale) {
        parent.querySelector('.product_price')?.classList?.remove('d-inline-block');
    }

    if (addToCartButton) {
        addToCartButton.dataset.subscriptionPlanId = combination.pricings.length > 0 ? combination.subscription_default_pricing_plan_id : '';
    }
    if (unit) {
        unit.textContent = combination.temporal_unit_display;
    }
    if (price) {
        price.textContent = combination.subscription_default_pricing_price;
    }
};

const oldGetOptionalCombinationInfoParam = VariantMixin._getOptionalCombinationInfoParam;
/**
 * Add the selected plan to the optional combination info parameters.
 *
 * @param {Element} product
 */
VariantMixin._getOptionalCombinationInfoParam = function (product) {
    const result = oldGetOptionalCombinationInfoParam.apply(this, arguments);
    Object.assign(result, {
        'plan_id': product?.querySelector('.product_price .plan_select input[name="plan_id"]:checked')?.value
    });

    return result;
};
