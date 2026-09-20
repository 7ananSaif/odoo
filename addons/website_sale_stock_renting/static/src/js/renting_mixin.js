import { _t } from "@web/core/l10n/translation";
import { RentingMixin } from '@website_sale_renting/js/renting_mixin';

const oldGetInvalidMessage = RentingMixin._getInvalidMessage;
/**
 * Override to take the stock renting availabilities into account.
 *
 * @override
 */
RentingMixin._getInvalidMessage = function (startDate, endDate, productId) {
    const message = oldGetInvalidMessage.apply(this, arguments);
    if (message || !startDate || !endDate || !this.rentingAvailabilities || this.preparationTime == undefined) {
        return message;
    }
    if (startDate < luxon.DateTime.now().plus({ hours: this.preparationTime })) {
        return _t("Your rental product cannot be prepared as fast, please rent later.");
    }
    return message;
};

const oldGetExpectedEndDate = RentingMixin._getExpectedEndDate;

/**
 * Override to take the stock renting preparation time into account.
 *
 * @override
 */
RentingMixin._getExpectedEndDate = function (endDate) {
    let end = oldGetExpectedEndDate.apply(this, arguments);
    if (this._isDurationWithHours() && this.preparationTime) {
        end = end.plus({ hours: this.preparationTime });
    }
    return end;
};
