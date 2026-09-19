import VariantMixin from '@website_sale/js/variant_mixin';
import { RentingMixin } from '@website_sale_renting/js/renting_mixin';

VariantMixin._isDurationWithHours = RentingMixin._isDurationWithHours;
VariantMixin._getRentingDates = RentingMixin._getRentingDates; // Needed for _getSerializedRentingDates
VariantMixin._getSerializedRentingDates = RentingMixin._getSerializedRentingDates;

const oldGetOptionalCombinationInfoParam = VariantMixin._getOptionalCombinationInfoParam;
/**
 * Add the renting pickup and return dates to the optional combination info parameters.
 *
 * @param {Element} product
 */
VariantMixin._getOptionalCombinationInfoParam = function (product) {
    const result = oldGetOptionalCombinationInfoParam.apply(this, arguments);

    Object.assign(result, this._getSerializedRentingDates(product));

    return result;
};


const oldOnChangeCombination = VariantMixin._onChangeCombination;
/**
 * Update the renting text when the combination change.
 *
 * @param {Event} ev
 * @param {Element} parent
 * @param {object} combination
 */
VariantMixin._onChangeCombination = function (ev, parent, combination) {
    oldOnChangeCombination.apply(this, arguments);
    if (!combination.is_rental) {
        return;
    }
    const unitListPrice = parent.querySelector('.o_rental_product_price del .oe_currency_value');
    const unitPrice = parent.querySelector('.o_rental_product_price strong .oe_currency_value');
    const price = parent.querySelector('.o_renting_price .oe_currency_value');
    const totalPrice = parent.querySelector('.o_renting_total_price .oe_currency_value');
    const rentingDetails = parent.querySelector('.o_renting_details');
    const duration = rentingDetails?.querySelector('.o_renting_duration');
    const unit = rentingDetails?.querySelector('.o_renting_unit');
    const precision = combination.currency_precision;
    if (unitListPrice) {
        unitListPrice.textContent = this._priceToStr(combination.list_price, precision);
    }
    if (unitPrice) {
        unitPrice.textContent = this._priceToStr(combination.price, precision);
    }
    if (price) {
        price.textContent = this._priceToStr(combination.current_rental_price_per_unit, precision);
    }
    if (totalPrice) {
        totalPrice.textContent = this._priceToStr(combination.current_rental_price, precision);
    }
    if (duration) {
        duration.textContent = combination.current_rental_duration;
    }
    if (unit) {
        unit.textContent = combination.current_rental_unit;
    }

    // Update pricing table
    const pricingTable = document.querySelector("#oe_wsale_rental_pricing_table tbody");
    if (pricingTable) {
        updatePricingTable(pricingTable, combination.pricing_table);
    }
};


function updatePricingTable(table, tableInfo) {
    let lines = table.querySelectorAll("tr");
    const neededLines = tableInfo.length;
    if (lines.length > neededLines) {
        let diff = lines.length - neededLines;
        while (diff) {
            lines[lines.length - diff--].remove();
        }
    } else if (lines.length < neededLines) {
        let diff = neededLines - lines.length;
        while (diff--) {
            const line = document.createElement("tr");
            const name = document.createElement("td");
            const price = document.createElement("td");
            name.classList.add("w-50");
            price.classList.add("w-50", "text-muted");
            line.appendChild(name);
            line.appendChild(price);
            table.appendChild(line);
        }
        lines = table.querySelectorAll("tr");
    }
    for (let idx = 0; idx < neededLines; idx++) {
        const info = tableInfo[idx];
        const line = lines[idx];
        line.querySelector("td:nth-of-type(1)").innerText = info[0];
        line.querySelector("td:nth-of-type(2)").innerText = info[1];
    }
};
