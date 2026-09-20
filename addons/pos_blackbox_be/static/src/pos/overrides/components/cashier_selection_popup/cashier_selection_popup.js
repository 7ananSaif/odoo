import { CashierSelectionPopup } from "@pos_hr/app/components/popups/cashier_selection_popup/cashier_selection_popup";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { deserializeDateTime, formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { is24HourFormat } from "@web/core/l10n/time";

const { DateTime } = luxon;

patch(CashierSelectionPopup.prototype, {
    setup() {
        super.setup();
        this.clockState = useState({ currentClockAction: null, cashierClockinDate: null });
        this.updateCashierClockinDate();
    },

    updateCashierClockinDate() {
        this.clockState.cashierClockinDate = this.computeCashierClockinDate();
    },

    get cashierClockinDate() {
        return this.isClockedIn(this.props.currentCashier) && this.clockState.cashierClockinDate;
    },

    computeCashierClockinDate() {
        const rawClockIn = this.pos.session._user_latest_clock_in;
        const employee = this.props.currentCashier;

        if (!rawClockIn || !employee || !this.isClockedIn(employee)) {
            return null;
        }

        const clockInTime = deserializeDateTime(rawClockIn);
        const now = DateTime.now();
        const diff = now.diff(clockInTime, ["hours", "minutes"]).toObject();

        const durationParts = [];
        if (diff.hours >= 1) {
            durationParts.push(
                `${Math.floor(diff.hours)} ${_t(diff.hours === 1 ? "hour" : "hours")}`
            );
        }
        if (diff.minutes >= 1) {
            durationParts.push(
                `${Math.floor(diff.minutes)} ${_t(diff.minutes === 1 ? "minute" : "minutes")}`
            );
        }
        const sinceTime = clockInTime.toFormat(is24HourFormat() ? "HH:mm" : "hh:mm a");
        let sinceLabel;
        if (clockInTime.hasSame(now, "day")) {
            //Today
            sinceLabel = sinceTime;
        } else if (clockInTime.hasSame(DateTime.now().minus({ days: 1 }), "day")) {
            // Yesterday
            sinceLabel = `${_t("Yesterday")} ${sinceTime}`;
        } else {
            sinceLabel = `${formatDate(clockInTime)} ${sinceTime}`;
        }

        return `${durationParts.join(", ")} (${_t("since %s", sinceLabel)})`;
    },

    isClockLoading(employee) {
        return this.clockState.currentClockAction === employee.id;
    },

    get isClockDisabled() {
        return this.clockState.currentClockAction && true;
    },

    isClockedIn(employee) {
        return this.pos.session._employees_clocked_ids?.includes(employee.id);
    },

    async clock(employee, clockIn) {
        if (this.isClockDisabled) {
            return;
        }
        this.clockState.currentClockAction = employee.id;
        try {
            await this.pos.clockEmployee(employee, clockIn);
            if (this.props.currentCashier?.id === employee.id) {
                this.updateCashierClockinDate();
            }
        } finally {
            this.clockState.currentClockAction = null;
        }
    },
});
