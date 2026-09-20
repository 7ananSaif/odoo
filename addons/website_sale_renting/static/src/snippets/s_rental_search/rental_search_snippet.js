import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { parseDate, parseDateTime, serializeDateTime } from '@web/core/l10n/dates';
import { redirect } from '@web/core/utils/urls';
import { RentingMixin } from '@website_sale_renting/js/renting_mixin';

export class RentalSearchSnippet extends Interaction {
    static selector = '.s_rental_search';
    dynamicContent = {
        '.s_rental_search_btn': { 't-on-click': this.onClickRentalSearchButton },
        '.o_website_sale_daterange_picker': { 't-on-toggle_search_btn': this.onToggleSearchBtn },
    };

    onToggleSearchBtn(ev) {
        ev.currentTarget.querySelector('.s_rental_search_btn').disabled = Boolean(ev.detail);
    }

    onClickRentalSearchButton() {
        const parse = this._isDurationWithHours() ? parseDateTime : parseDate;
        const startInput = this.el.querySelector('input[name=renting_start_date]');
        const endInput = this.el.querySelector('input[name=renting_end_date]');
        this.searchRentals({ detail: {
            startDate: parse(startInput.value),
            endDate: parse(endInput.value),
        }});
    }

    /**
     * This function is triggered when the user clicks on the rental search button.
     *
     * @param {CustomEvent} event
     */
    searchRentals(event) {
        const { startDate, endDate } = event.detail;
        const searchParams = new URLSearchParams();
        if (startDate && endDate) {
            searchParams.append('start_date', serializeDateTime(startDate));
            searchParams.append('end_date', serializeDateTime(endDate));
        }
        const productAttributeId = this.el.querySelector('.product_attribute_search_rental_name').id;

        const productAttributeValueId = this.el.querySelector('.s_rental_search_select').value;
        if (productAttributeValueId) {
            searchParams.append('attribute_values', `${productAttributeId}-${productAttributeValueId}`);
        }
        redirect(`/shop?${searchParams.toString()}`);
    }
}

// TODO(loti): temporary hack. RentingMixin should be converted to a class after converting/deleting
// VariantMixin.
Object.assign(RentalSearchSnippet.prototype, RentingMixin);

registry
    .category('public.interactions')
    .add('website_sale_renting.rental_search_snippet', RentalSearchSnippet);
