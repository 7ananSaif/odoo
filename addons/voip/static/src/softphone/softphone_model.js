import { InCallViewModel } from "@voip/softphone/in_call_view_model";
import { KeypadModel } from "@voip/softphone/keypad_model";
import { isSubstring, matchPhoneNumber } from "@voip/utils/utils";

/**
 * Retains the state of the Softphone that needs to be persisted even if the
 * corresponding component is unmounted.
 */
export class Softphone {
    activeTab = "dialer";
    activeTabSection = "";
    activeRecord = null;
    dialer = new KeypadModel();
    isDisplayed = false;
    addressBook = {
        searchInputValue: "",
    };
    agenda = {
        searchInputValue: "",
    };
    callSummary = {
        /**
         * @type {import("@voip/core/call_model").Call}
         */
        call: null,
        isShown: false,
        hideAfterTimeout: undefined,
        scrollToActiveRecord: false,
    };
    history = {
        searchInputValue: "",
    };
    inCallView = new InCallViewModel();
    shouldFocus = false;

    constructor(store, voip) {
        this.store = store;
        this.voip = voip;
        this.setup();
    }

    get activities() {
        const searchInputValue = this.agenda.searchInputValue.trim();
        return Object.values(this.store["mail.activity"].records).filter(
            (activity) =>
                activity.activity_category === "phonecall" &&
                ["today", "overdue"].includes(activity.state) &&
                activity.phone &&
                activity.user_id.eq(this.store.self.main_user_id) &&
                (!searchInputValue ||
                    [activity.partner.name, activity.partner.displayName, activity.name].some((x) =>
                        isSubstring(x, searchInputValue)
                    ) ||
                    matchPhoneNumber(activity.phone, searchInputValue))
        );
    }

    get contacts() {
        return Object.values(this.store["res.partner"].records).filter((partner) =>
            Boolean(partner.phone)
        );
    }

    /**
     * Setup method to be overridden by subclasses.
     * This method exists because the constructor cannot be overridden,
     * allowing subclasses to perform initialization logic.
     */
    setup() {}

    hide() {
        this.isDisplayed = false;
    }

    hideCallSummary() {
        clearTimeout(this.callSummary.hideAfterTimeout);
        Object.assign(this.callSummary, {
            call: null,
            hideAfterTimeout: undefined,
            isShown: false,
        });
    }

    show() {
        this.isDisplayed = true;
        this.shouldFocus = true;
    }

    showSummary(call) {
        clearTimeout(this.callSummary.hideAfterTimeout);
        Object.assign(this.callSummary, {
            call,
            hideAfterTimeout: setTimeout(() => {
                this.hideCallSummary();
                this.callSummary.scrollToActiveRecord = true;
            }, 3000),
            isShown: true,
        });
    }
}
