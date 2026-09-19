import { fields, Record } from "@mail/core/common/record";

import { deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";

export class Call extends Record {
    static id = "id";
    static _name = "voip.call";
    /** @type {Object.<number, Call>} */
    static records = {};

    /**
     * @param {Object} data
     * @returns {Call}
     */
    update(data) {
        super.update(...arguments);
        if (data.partner_id) {
            this.partner_id = this.store["res.partner"].insert(data.partner_id);
        }
        if (data.create_date) {
            this.create_date = deserializeDateTime(data.create_date);
        }
        if (data.start_date) {
            this.start_date = deserializeDateTime(data.start_date);
        }
        if (data.end_date) {
            this.end_date = deserializeDateTime(data.end_date);
        }
    }

    activity;
    /** @type {luxon.DateTime} */
    create_date;
    /** @type {"incoming"|"outgoing"} */
    direction;
    /** @type {string} */
    display_name;
    /** @type {luxon.DateTime} */
    end_date;
    partner_id;
    /** @type {import("@mail/core/country_model").Country | undefined} */
    phone_country_id = fields.One("res.country");
    /** @type {string} */
    phone_number;
    /** @type {luxon.DateTime} */
    start_date;
    /** @type {"aborted"|"calling"|"missed"|"ongoing"|"rejected"|"terminated"} */
    state = fields.Attr("calling", {
        onUpdate() {
            switch (this.state) {
                case "aborted":
                case "missed":
                case "rejected":
                case "terminated": {
                    this.onCallEnd();
                    break;
                }
                default:
                    return;
            }
        },
    });
    /** @type {{ interval: number, time: number }} */
    timer;

    /** @returns {string} */
    get callDate() {
        if (this.state === "terminated") {
            return this.start_date.toLocaleString(luxon.DateTime.TIME_SIMPLE);
        }
        return this.create_date.toLocaleString(luxon.DateTime.TIME_SIMPLE);
    }

    /** @returns {number} */
    get duration() {
        if (!this.start_date || !this.end_date) {
            return 0;
        }
        return (this.end_date - this.start_date) / 1000;
    }

    /** @returns {string} */
    get durationString() {
        return this._formatTimerText(this.duration);
    }

    /** @returns {boolean} */
    get isInProgress() {
        switch (this.state) {
            case "calling":
            case "ongoing":
                // In case the power goes out in the middle of a call (for
                // example), the call may be stuck in the “calling” or “ongoing”
                // state, meaning we can't rely on the state alone, hence the
                // need to also check for the session.
                return Boolean(
                    this.store.env.services["voip.user_agent"].activeSession?.call.eq(this)
                );
            default:
                return false;
        }
    }

    /** @returns {string} */
    get timerText() {
        return this._formatTimerText(this.timer?.time);
    }

    onCallEnd() {
        const softphone = this.store.env.services.voip.softphone;
        const userAgent = this.store.env.services["voip.user_agent"];
        if (!userAgent.mainSession?.call && !userAgent.transferSession?.call) {
            return;
        }
        if (this.eq(userAgent.mainSession?.call)) {
            userAgent.mainSession = userAgent.transferSession;
            userAgent.transferSession = null;
        } else if (this.eq(userAgent.transferSession?.call)) {
            userAgent.transferSession = null;
        } else {
            return;
        }
        userAgent.activeSession = userAgent.mainSession;
        if (!userAgent.activeSession) {
            softphone.showSummary(this);
            softphone.dialer.reset();
            softphone.inCallView.reset();
        }
    }

    /**
     * @param {number|undefined} seconds
     * @returns {string}
     */
    _formatTimerText(seconds) {
        if (!seconds) {
            return _t("%(minutes)s:%(seconds)s", { minutes: "00", seconds: "00" });
        }
        if (seconds < 3600) {
            return _t("%(minutes)s:%(seconds)s", {
                minutes: String(Math.floor(seconds / 60)).padStart(2, "0"),
                seconds: String(seconds % 60).padStart(2, "0"),
            });
        }
        return _t("%(hours)s:%(minutes)s:%(seconds)s", {
            hours: String(Math.floor(seconds / 3600)).padStart(2, "0"),
            minutes: String(Math.floor((seconds % 3600) / 60)).padStart(2, "0"),
            seconds: String(seconds % 60).padStart(2, "0"),
        });
    }
}

Call.register();
