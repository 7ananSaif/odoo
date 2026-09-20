import { Component, useEffect, useRef } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { scrollTo } from "@web/core/utils/scrolling";

export class TabEntry extends Component {
    static defaultProps = { extraClass: "", subtitleClass: "" };
    static props = {
        avatarUrl: { type: String },
        extraClass: { type: String, optional: true },
        title: { type: String },
        subtitle: { type: String, optional: true },
        subtitleClass: { type: String, optional: true },
        subtitleIcon: { type: String, optional: true },
        phoneNumber: { type: String },
        record: Object,
        /**
         * The name of the section of the tab to which this entry belongs.
         */
        section: String,
        slots: Object,
    };
    static template = "voip.TabEntry";

    setup() {
        this.softphone = useService("voip").softphone;
        this.activeRecordRef = useRef("active-record");
        useEffect(
            (scrollToActiveRecord) => {
                if (!scrollToActiveRecord || !this.activeRecordRef.el) {
                    return;
                }
                scrollTo(this.activeRecordRef.el);
                this.softphone.callSummary.scrollToActiveRecord = false;
            },
            () => [this.softphone.callSummary.scrollToActiveRecord]
        );
        useEffect(
            (isActiveRecord) => {
                if (!isActiveRecord || !this.activeRecordRef.el) {
                    return;
                }
                scrollTo(this.activeRecordRef.el);
            },
            () => [this.isActiveRecord]
        );
    }

    /** @returns {string} */
    get flagAlt() {
        return _t("%(country)s flag", { country: this.props.record.phone_country_id.name });
    }

    /** @returns {boolean} */
    get isActiveRecord() {
        return (
            this.softphone.activeTabSection === this.props.section &&
            this.props.record.eq(this.softphone.activeRecord)
        );
    }

    /**
     * Updates the active section and the active record. These two variables
     * determine which record to unfold and which record to return to after the
     * call summary is hidden.
     *
     * @param {MouseEvent} ev
     */
    onClickSummary(ev) {
        if (this.isActiveRecord) {
            this.softphone.activeRecord = null;
            this.softphone.activeTabSection = "";
        } else {
            this.softphone.activeTabSection = this.props.section;
            this.softphone.activeRecord = this.props.record;
        }
    }
}
