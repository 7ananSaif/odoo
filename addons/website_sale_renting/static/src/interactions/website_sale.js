import {
    deserializeDateTime,
    formatDate,
    formatDateTime,
    serializeDateTime,
} from '@web/core/l10n/dates';
import { rpc } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';
import { redirect } from '@web/core/utils/urls';
import { patchDynamicContent } from '@web/public/utils';
import wSaleUtils from '@website_sale/js/website_sale_utils';
import { WebsiteSale } from '@website_sale/interactions/website_sale';
import { RentingMixin } from '@website_sale_renting/js/renting_mixin';

patch(WebsiteSale.prototype, RentingMixin);
patch(WebsiteSale.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            _root: {
                't-on-renting_constraints_changed': this.onRentingConstraintsChanged.bind(this),
                't-on-toggle_disable': this.onToggleDisable.bind(this),
                't-on-daterangepicker_apply': this.onDatePickerApply.bind(this),
            },
            '.js_main_product .o_website_sale_daterange_picker': {
                't-on-change': this.onChangeVariant.bind(this),
            },
            '.clear-daterange': { 't-on-click': this.onDatePickerClear.bind(this) },
        });
        this.el.querySelectorAll('[data-bs-toggle="tooltip"].o_rental_info_message').forEach(el => {
            const tooltip = window.Tooltip.getOrCreateInstance(el);
            this.registerCleanup(() => tooltip.dispose());
        });
    },

    async _checkNewDatesOnCart() {
        const { start_date, end_date, values } = await this.waitFor(rpc(
            '/shop/cart/update_renting', this._getSerializedRentingDates()
        )) ?? {};
        if (!values) {
            return;
        }
        // `updateCartNavBar` regenerates the cart lines so we need to stop and start interactions
        // to make sure the regenerated reorder products and cart lines are properly handled.
        const cart = this.el.querySelector('#shop_cart');
        this.services['public.interactions'].stopInteractions(cart);
        wSaleUtils.updateCartNavBar(values);
        this.services['public.interactions'].startInteractions(cart);
        const format = this._isDurationWithHours() ? formatDateTime : formatDate;
        document.querySelector("input[name=renting_start_date]").value = format(deserializeDateTime(start_date, { tz: this.websiteTz }), { tz: this.websiteTz });
        document.querySelector("input[name=renting_end_date]").value = format(deserializeDateTime(end_date, { tz: this.websiteTz }), { tz: this.websiteTz });
    },

    /**
     * Override of `_updateRootProduct` to add the renting dates to the rootProduct for rental
     * products.
     *
     * @override
     * @private
     * @param {HTMLFormElement} form - The form in which the product is.
     *
     * @returns {void}
     */
    _updateRootProduct(form) {
        super._updateRootProduct(...arguments);
        Object.assign(this.rootProduct, this._getSerializedRentingDates());
    },

    /**
     * During click, verify the renting periods and disable the datimepicker as soon as rental
     * product is added to cart.
     */
    async onClickAdd(ev) {
        const form = wSaleUtils.getClosestProductForm(ev.currentTarget);
        if (form.querySelector('input[name="is_rental"]')?.value) {
            if (!this._verifyValidRentingPeriod(form)) {
                ev.stopPropagation();
                return Promise.resolve();
            }
        }

        const quantity = await this.waitFor(super.onClickAdd(...arguments));
        const datepickerElements = document.querySelectorAll('.o_website_sale_daterange_picker_input');
        const clearBtnElements = document.querySelectorAll('.clear-daterange');
        const infoMessageElements = document.querySelectorAll('.o_rental_info_message');
        if (quantity > 0) {
            datepickerElements.forEach((elements) => {
                elements.disabled=true;
            });
            clearBtnElements.forEach((elements) => {
                elements.classList.add('d-none');
            });
            infoMessageElements.forEach((elements) => {
                elements.classList.remove('d-none');
            });
        }

        return quantity;
    },

    /**
     * Update the instance value when the renting constraints changes.
     *
     * @param {CustomEvent} event
     */
    onRentingConstraintsChanged(event) {
        const info = event.detail;
        if (info.rentingUnavailabilityDays) {
            this.rentingUnavailabilityDays = info.rentingUnavailabilityDays;
        }
        if (info.rentingMinimalTime) {
            this.rentingMinimalTime = info.rentingMinimalTime;
        }
        if (info.websiteTz) {
            this.websiteTz = info.websiteTz;
        }
        if (info.rentingAvailabilities) {
            this.rentingAvailabilities = info.rentingAvailabilities;
        }
    },

    /**
     * Handler to call the function which toggles the disabled class
     * depending on the parent element and the availability of the current combination.
     *
     * @param {CustomEvent} event event
     */
    onToggleDisable(event) {
        const { parent, isCombinationAvailable } = event.detail;
        this._toggleDisable(parent, isCombinationAvailable);
    },

    /**
     * Verify that the dates given in the daterange picker are valid and display a message if not.
     *
     * @param {Element} parent
     * @private
     */
    _verifyValidRentingPeriod(parent) {
        const rentingDates = this._getRentingDates();
        if (!this._verifyValidInput(rentingDates, 'start_date') ||
            !this._verifyValidInput(rentingDates, 'end_date')) {
            return false;
        }
        const form = wSaleUtils.getClosestProductForm(parent);
        const message = this._getInvalidMessage(
            rentingDates.start_date, rentingDates.end_date, this._getProductId(form)
        );
        if (message) {
            this.el.querySelector('span[name=renting_warning_message]').innerText = message;
        }
        this.el.querySelector('.o_renting_warning').classList.toggle('d-block', !!message);
        this._toggleDisable(form, !message);
        return !message;
    },

    /**
     * Verify the renting date extracted from input is valid.
     *
     * @param {object} rentingDates
     * @param {string} inputName
     */
    _verifyValidInput(rentingDates, inputName) {
        const input = this.el.querySelector('input[name=renting_' + inputName + ']');
        if (input) {
            input.classList.toggle('is-invalid', !rentingDates[inputName]);
        }
        return rentingDates[inputName];
    },

    /**
     * Verify the Renting Period on combination change.
     *
     * @param {Event} ev
     * @param {Element} parent
     * @param {Object} combination
     * @returns
     */
    _onChangeCombination(ev, parent, combination) {
        super._onChangeCombination(...arguments);
        if (!!combination.is_rental) {
            // only verify the renting dates if product can be rented
            this._verifyValidRentingPeriod(parent);
        }
    },

    /**
     * @param {CustomEvent} event
     */
    onDatePickerApply(event) {
        const { startDate, endDate } = event.detail;
        if (document.querySelector('.oe_cart')) {
            if (startDate && endDate) {
                this._checkNewDatesOnCart();
            }
        } else if (document.querySelector('.o_website_sale_shop_daterange_picker')) {
            this._addDatesToQuery(startDate, endDate);
        }
    },

    /**
     * Redirect to the shop page with the appropriate dates as search params.
     */
    _addDatesToQuery(start_date, end_date) {
        // get current URL parameters
        const searchParams = new URLSearchParams(window.location.search);
        if (start_date && end_date) {
            searchParams.set("start_date", serializeDateTime(start_date));
            searchParams.set("end_date", serializeDateTime(end_date));
        }
        redirect(`/shop?${searchParams.toString()}`);
    },

    onDatePickerClear(ev) {
        const searchParams = new URLSearchParams(window.location.search);
        searchParams.delete('start_date');
        searchParams.delete('end_date');
        window.location.search = searchParams.toString();
    },
});
