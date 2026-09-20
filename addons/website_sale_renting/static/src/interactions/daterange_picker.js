import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { areDatesEqual, deserializeDateTime, serializeDateTime } from '@web/core/l10n/dates';
import { rpc } from '@web/core/network/rpc';
import wSaleUtils from '@website_sale/js/website_sale_utils';

import { unitMapping, RentingMixin } from '@website_sale_renting/js/renting_mixin';

const { DateTime } = luxon;

export class DaterangePicker extends Interaction {
    static selector = '.o_website_sale_daterange_picker';
    rentingAvailabilities = {};

    setup() {
        // Whether this daterange picker is available on /shop.
        this.isShopDatePicker = this.el.classList.contains('o_website_sale_shop_daterange_picker');
        this.disableDateTimePickers = [];
    }

    /**
     * During start, load the renting constraints to validate renting pickup and return dates.
     */
    async willStart() {
        await this._loadRentingConstraints();
    }

    /**
     * Start the website_sale daterange picker and save in the instance the value of the default
     * renting pickup and return dates, which could be undefined.
     */
    start() {
        this.startDate = this._getDefaultRentingDate('start_date');
        this.endDate = this._getDefaultRentingDate('end_date');
        this.el.querySelectorAll('.o_daterange_picker').forEach(
            (el) => this._initSaleRentingDateRangePicker(el)
        );
        this._verifyValidPeriod();
    }

    destroy() {
        for (const disableDateTimePicker of this.disableDateTimePickers) {
            disableDateTimePicker();
        }
    }

    /**
     * Checks if the default renting dates are set.
     * @returns {*}
     * @private
     */
    _hasDefaultDates() {
        return (this._getSearchDefaultRentingDate('start_date') && this._getSearchDefaultRentingDate('end_date'))
               ||
               (this.el.querySelector('input[name="default_start_date"]') && this.el.querySelector('input[name="default_end_date"]'));
    }

    /**
     * Load renting constraints.
     *
     * The constraints are the days where no pickup nor return can be processed and the minimal
     * duration of a renting.
     *
     * @private
     */
    async _loadRentingConstraints() {
        const constraints = await this.waitFor(rpc('/rental/product/constraints'));
        this.rentingUnavailabilityDays = constraints.renting_unavailabity_days;
        this.rentingMinimalTime = constraints.renting_minimal_time;
        this.websiteTz = constraints.website_tz;
        this._triggerRentingConstraintsChanged({
            rentingUnavailabilityDays: this.rentingUnavailabilityDays,
            rentingMinimalTime: this.rentingMinimalTime,
            websiteTz: this.websiteTz,
        });
    }

    /**
     * Initialize renting date input and attach to it a daterange picker object.
     *
     * A method is attached to the daterange picker in order to handle the changes.
     *
     * @param {HTMLElement} el
     * @private
     */
    _initSaleRentingDateRangePicker(el) {
        const hasDefaultDates = Boolean(this._hasDefaultDates());
        el.dataset.hasDefaultDates = hasDefaultDates;
        const value =
            this.isShopDatePicker && !hasDefaultDates ? ['', ''] : [this.startDate, this.endDate];
        const datetimeWebsiteTz = DateTime.now().setZone(this.websiteTz);
        this.disableDateTimePickers.push(this.services['datetime_picker'].create(
            {
                target: el,
                pickerProps: {
                    value,
                    range: true,
                    // overnight period in hours but not selectable
                    type: this._canSelectHours() ? 'datetime' : 'date',
                    minDate: DateTime.min(datetimeWebsiteTz, this.startDate),
                    maxDate: DateTime.max(datetimeWebsiteTz.plus({ years: 3 }), this.endDate),
                    isDateValid: this._isValidDate.bind(this),
                    dayCellClass: (date) => this._isCustomDate(date, this.startDate).join(' '),
                    tz: this.websiteTz,
                },
                onApply: ([startDate, endDate]) => {
                    // User cannot choose the time, using the previously set time
                    if (!this._canSelectHours() && this._isDurationWithHours()) {
                        const [pickupHour, pickupMinute] = this._getPickupTime();
                        const startDateWithTime = startDate.set({
                            hour: pickupHour,
                            minute: pickupMinute,
                        });
                        const [returnHour, returnMinute] = this._getReturnTime();
                        const endDateWithTime = endDate.set({
                            hour: returnHour,
                            minute: returnMinute,
                        });
                        if (areDatesEqual([this.startDate, this.endDate], [startDateWithTime, endDateWithTime])) {
                            return;
                        }
                        this.startDate = startDateWithTime;
                        this.endDate = endDateWithTime;
                    }
                    else {
                        if (areDatesEqual([this.startDate, this.endDate], [startDate, endDate])) {
                            return;
                        }
                        this.startDate = startDate;
                        this.endDate = endDate;
                    }
                    this._verifyValidPeriod();
                    this.el.querySelector('input[name=renting_start_date]')
                        .dispatchEvent(new Event('change', { bubbles: true }));
                    this.el.dispatchEvent(new CustomEvent(
                        'daterangepicker_apply', { detail: { startDate: this.startDate, endDate: this.endDate }, bubbles: true },
                    ));
                },
                getInputs: () => [
                    el.querySelector('input[name=renting_start_date]'),
                    el.querySelector('input[name=renting_end_date]'),
                ],
            },
        ).enable());
    }

    async _fetchProductAvailabilities(productId, minDate, maxDate) {
        const result = await this.waitFor(rpc('/rental/product/availabilities', {
            product_id: productId,
            min_date: minDate,
            max_date: maxDate,
        }));
        this.rentingAvailabilities[productId] = [];
        if (result.renting_availabilities?.length) {
            this.rentingAvailabilities[productId] = result.renting_availabilities.map(
                (rentingAvailabilities) => {
                    const { start, end, ...rest } = rentingAvailabilities;
                    return {
                        start: deserializeDateTime(start),
                        end: deserializeDateTime(end),
                        ...rest,
                    };
                }
            );
        }
        // `preparation_time` is only populated/used in website_sale_stock_renting. It has no effect
        // in website_sale_renting, but we keep it here for simplicity.
        this.preparationTime = result.preparation_time;
    }

    /**
     * Get the default renting date from the hidden input filled server-side.
     *
     * @param {String} inputName - The name of the input tag that contains pickup or return date
     * @private
     */
    _getDefaultRentingDate(inputName) {
        let defaultDate = this._getSearchDefaultRentingDate(inputName);
        if (defaultDate) {
            return deserializeDateTime(defaultDate);
        }
        // that means that the date is not in the url
        const defaultDateEl = this.el.querySelector(`input[name="default_${inputName}"]`);
        if (defaultDateEl) {
            return deserializeDateTime(defaultDateEl.value, { tz: this.websiteTz });
        }
        if (this.startDate) {
            // that means that the start date is already set
            const { duration, unit } = this.rentingMinimalTime;
            const minEndDate = this.startDate.plus({ [unitMapping[unit]]: duration });
            const defaultEndDate = this.startDate.plus({ days: 1 });
            const endDate = DateTime.max(minEndDate, defaultEndDate);
            return this._getFirstAvailableDate(endDate);
        }
        // that means that the date is not in the url and not in the hidden input
        // get the first available date based on this.rentingUnavailabilityDays
        const date = DateTime.now().plus({ days: 1, hours: 1 }).set({minutes: 0, seconds: 0 });
        return this._getFirstAvailableDate(date);
    }

    /**
     * Get the default renting date for the given input from the search params.
     *
     * @param {String} inputName - The name of the input tag that contains pickup or return date
     * @private
     */
    _getSearchDefaultRentingDate(inputName) {
        return new URLSearchParams(window.location.search).get(inputName);
    }

    /**
     * Check if the date is valid.
     *
     * This function is used in the daterange picker objects and meant to be easily overriden.
     *
     * @param {DateTime} date
     * @private
     */
    _isValidDate(date) {
        return !this.rentingUnavailabilityDays[date.weekday];
    }

    /**
     * Set Custom CSS to a given daterangepicker cell
     *
     * This function is used in the daterange picker objects and meant to be easily overriden.
     *
     * @param {DateTime} date
     * @private
     */
    _isCustomDate(date, startDate) {
        const result = [];
        const productId = this._getProductId();
        if (!productId || !this.rentingAvailabilities[productId]) {
            return result;
        }
        // Consider the pickup time to check the availability
        const dateStart = date.set({hour: startDate.hour, minute: startDate.minute});
        for (const interval of this.rentingAvailabilities[productId]) {
            if (interval.start > dateStart) {
                return result;
            }
            if (interval.end > dateStart && interval.quantity_available <= 0) {
                result.push('o_daterangepicker_danger');
                return result;
            }
        }
        return result;
    }

    /**
     * Verify that the dates given in the daterange picker are valid and display a message if not.
     *
     * @private
     */
    _verifyValidPeriod() {
        const message = this._getInvalidMessage(this.startDate, this.endDate, this._getProductId());
        if (message) {
            this.el.parentElement.querySelector('span[name=renting_warning_message]').innerText = message;
            this.el.parentElement.querySelector('.o_renting_warning').classList.add('d-block');
        } else {
            this.el.parentElement.querySelector('.o_renting_warning').classList.remove('d-block');
        }
        const form = wSaleUtils.getClosestProductForm(this.el);
        if (form) {
            document.querySelector('.oe_website_sale')?.dispatchEvent(new CustomEvent(
                'toggle_disable', { detail: { parent: form, isCombinationAvailable: !message }}
            ));
        }
        this.el.dispatchEvent(new CustomEvent(
            'toggle_search_btn', { bubbles: true, detail: message }
        ));
        return !message;
    }

    /**
     * Get the product id from the dom if not initialized.
     */
    _getProductId() {
        if (!this.productId) {
            const productSelector = [
                'input[type="hidden"][name="product_id"]',
                'input[type="radio"][name="product_id"]:checked',
            ];
            const form = wSaleUtils.getClosestProductForm(this.el);
            const productInput = form && form.querySelector(productSelector.join(', '));
            this.productId = productInput && parseInt(productInput.value);
        }
        return this.productId;
    }

    /**
     * Get the first available date based on this.rentingUnavailabilityDays.
     * @private
     */
    _getFirstAvailableDate(date) {
        let counter = 0;
        while (!this._isValidDate(date) && counter < 1000) {
            date = date.plus({days: 1});
            counter++;
        }
        return date;
    }

    _triggerRentingConstraintsChanged(vals) {
        document.querySelector('.oe_website_sale')?.dispatchEvent(new CustomEvent(
            'renting_constraints_changed', { detail: vals || {} }
        ));
    }

    /**
     * Update the renting availabilities dict with the unavailabilities of the current product
     *
     * @private
     */
    async _updateRentingProductAvailabilities() {
        const productId = this._getProductId();
        if (!productId || this.rentingAvailabilities[productId]) {
            return;
        }
        await this.waitFor(this._fetchProductAvailabilities(
            productId,
            serializeDateTime(luxon.DateTime.now()),
            serializeDateTime(luxon.DateTime.now().plus({ years: 3 }))
        ));
        this._triggerRentingConstraintsChanged({
            rentingAvailabilities: this.rentingAvailabilities,
            preparationTime: this.preparationTime,
        });
        this._verifyValidPeriod();
    }
}

// TODO(loti): temporary hack. RentingMixin should be converted to a class after converting/deleting
// VariantMixin.
Object.assign(DaterangePicker.prototype, RentingMixin);

registry
    .category('public.interactions')
    .add('website_sale_renting.daterange_picker', DaterangePicker);
