import { useSelection } from "@mail/utils/common/hooks";

import { Component, markup, useEffect, useRef } from "@odoo/owl";

import { KeypadModel } from "@voip/softphone/softphone_model";
import { tabComponents } from "@voip/softphone/tab";
import { isCurrentFocusEditable, matchPhoneNumber } from "@voip/utils/utils";

import { isMobileOS } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import { normalize, normalizedMatch } from "@web/core/l10n/utils";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { htmlJoin } from "@web/core/utils/html";
import { useDebounced } from "@web/core/utils/timing";

const T9_MAPPING = Object.freeze({
    2: "ABC",
    3: "DEF",
    4: "GHI",
    5: "JKL",
    6: "MNO",
    7: "PQRS",
    8: "TUV",
    9: "WXYZ",
});

/**
 * The actual keypad, its search bar, and recipient suggestions.
 */
export class Keypad extends Component {
    static components = { ...tabComponents };
    static defaultProps = { dtmf: false };
    static props = {
        dtmf: { type: Boolean, optional: true },
        onClickBack: { type: Function, optional: true },
        onClickFirstResult: { type: Function, optional: true },
        onClickTransferPhone: { type: Function, optional: true },
        state: KeypadModel,
        slots: { type: Object, optional: true },
    };
    static template = "voip.Keypad";

    setup() {
        this.action = useService("action");
        this.userAgent = useService("voip.user_agent");
        this.voip = useService("voip");
        this.inputRef = useRef("input-ref");
        this.selection = useSelection({
            refName: "input-ref",
            model: this.props.state.input.selection,
            preserveOnClickAwayPredicate: (ev) =>
                Boolean(ev.target.closest(".o-voip-Keypad-backspace, .o-voip-Keypad-digitBtn")),
        });
        this.ui = useService("ui");
        this.softphone = useService("voip").softphone;
        this.isMobile = isMobileOS(); // TODO unused, remove in master
        useEffect(
            (shouldFocusInput) => {
                if (
                    shouldFocusInput &&
                    this.inputRef.el &&
                    !this.voip.error &&
                    (document.activeElement === this.inputRef.el || !isCurrentFocusEditable())
                ) {
                    // By default, the <input> is rendered with "none" as
                    // inputMode, which should ensure that no update from OWL
                    // would open the keyboard. We also re-force "none" here, in
                    // the function that controls the focus. We only set to
                    // "text" when the user actually engages with the input
                    // using his finger. As soon as the input will change in any
                    // other way than using the mobile keyboard, this will be
                    // switched back to "none".
                    this.inputRef.el.inputMode = "none";

                    this.inputRef.el.focus();
                    this.selection.restore();
                    this.props.state.input.focus = false;
                }
            },
            () => [this.props.state.input.focus]
        );
        this.onInputDebounced = useDebounced((ev) => {
            this.onInputSearchBar(ev);
            this.updateCountryCode();
        }, 300);
    }

    get keys() {
        return [
            { key: "1", letters: "" },
            { key: "2", letters: "ABC" },
            { key: "3", letters: "DEF" },
            { key: "4", letters: "GHI" },
            { key: "5", letters: "JKL" },
            { key: "6", letters: "MNO" },
            { key: "7", letters: "PQRS" },
            { key: "8", letters: "TUV" },
            { key: "9", letters: "WXYZ" },
            { key: "*", letters: "", icon: "fa-asterisk" },
            { key: "0", letters: "+" },
            { key: "#", letters: "", icon: "fa-hashtag" },
        ];
    }

    get calleeSuggestions() {
        const searchTerms = this.props.state.input.value.trim();
        if (!searchTerms) {
            return { length: 0 };
        }
        const uniqueMatches = new Set();
        const nameMatched = [];
        const phoneNumberMatched = [];
        const containsLetters = /[A-Z]/i.test(searchTerms);
        const looksLikeT9 = [...searchTerms].every((letter) => letter in T9_MAPPING);
        for (const contact of this.voip.softphone.contacts) {
            if (containsLetters) {
                const match = highlightMatch(contact.name, searchTerms);
                if (!match) {
                    continue;
                }
                uniqueMatches.add(contact.id);
                nameMatched.push({
                    contact,
                    id: contact.id + " (by name)",
                    match,
                });
                // Since it contains letters, it's neither a T9 code nor a phone
                // number: no need to go further.
                continue;
            }
            if (looksLikeT9 && contact.t9_name) {
                const t9NameParts = contact.t9_name.trim().split(" ");
                for (let i = 0; i < t9NameParts.length; ++i) {
                    if (!t9NameParts[i].startsWith(searchTerms)) {
                        continue;
                    }
                    const nameParts = contact.name.split(" ");
                    const match = highlightT9Match(nameParts[i], searchTerms);
                    if (!match) {
                        console.warn(
                            `Unexpected mismatch between name and t9_name: "${contact.name}" and "${contact.t9_name}"`
                        );
                        break;
                    }
                    uniqueMatches.add(contact.id);
                    nameMatched.push({
                        contact,
                        id: contact.id + " (by name)",
                        match: htmlJoin(
                            [...nameParts.slice(0, i), match, ...nameParts.slice(i + 1)],
                            " "
                        ),
                    });
                    break;
                }
            }
            const phoneMatch = matchPhoneNumber(contact.phone, searchTerms);
            if (!phoneMatch) {
                continue;
            }
            const { before, match, after } = phoneMatch;
            uniqueMatches.add(contact.id);
            phoneNumberMatched.push({
                contact,
                id: contact.id + " (by phone)",
                match: markup`${before}<span class="o-voip-highlighted-letter fw-bolder">${match}</span>${after}`,
            });
        }
        const length = uniqueMatches.size;
        let firstResult = null;
        if (length > 0) {
            firstResult = nameMatched[0] ?? phoneNumberMatched[0];
        }
        const searchResultsBySearchField = new Map();
        if (nameMatched.length > 0) {
            searchResultsBySearchField.set(_t("Name"), nameMatched);
        }
        if (phoneNumberMatched.length > 0) {
            searchResultsBySearchField.set(_t("Phone number"), phoneNumberMatched);
        }
        return { length, firstResult, searchResultsBySearchField };
    }

    /** @returns {ReturnType<markup>} */
    get firstSuggestion() {
        const suggestion = this.calleeSuggestions.firstResult;
        const isMatchByName = suggestion.id.endsWith("(by name)");
        if (isMatchByName) {
            return markup`${suggestion.match} (${suggestion.contact.phone})`;
        }
        return markup`${suggestion.contact.voipName} (${suggestion.match})`;
    }

    get flagAltLabel() {
        if (!this.props.state.input.country) {
            return "";
        }
        return _t("%(country)s flag", { country: this.props.state.input.country.name });
    }

    /** @returns {string} */
    get inputFontSizeClass() {
        const length = this.props.state.input.value.length;
        if (!length) {
            return "fs-2";
        }
        if (length < 12) {
            return "fs-1";
        }
        if (length < 18) {
            return "fs-2";
        }
        return "fs-3";
    }

    /**
     * Determines whether the cached country code (if any) still matches the
     * contents of the keypad input. Useful for hiding the flag and redoing the
     * request if the content of the input changes.
     *
     * @returns {boolean}
     */
    get phoneNumberStartsWithCountryCode() {
        if (!this.props.state.input.country) {
            return false;
        }
        let phoneNumber = this.props.state.input.value.trim();
        if (phoneNumber.startsWith("00")) {
            phoneNumber = phoneNumber.slice(2);
        } else if (phoneNumber.startsWith("+")) {
            phoneNumber = phoneNumber.slice(1);
        } else {
            return false;
        }
        return phoneNumber.startsWith(this.props.state.input.country.phone_code);
    }

    get showOthersButtonText() {
        const numberOfOthers = this.calleeSuggestions.length - 1;
        switch (numberOfOthers) {
            case -1:
            case 0:
                return "";
            case 1:
                return _t("1 other…");
            case 2:
                return _t("2 others…");
            default:
                return _t("%s others…", numberOfOthers);
        }
    }

    getTitle(entry) {
        const isMatchByName = entry.id.endsWith("(by name)");
        return isMatchByName ? entry.match : entry.contact.voipName;
    }

    getSubtitle(entry) {
        const isMatchByPhone = entry.id.endsWith("(by phone)");
        return isMatchByPhone ? entry.match : entry.contact.phone;
    }

    onClickActivity(contact) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_id: false,
            res_model: "mail.activity",
            views: [[false, "form"]],
            view_mode: "form",
            target: "new",
            context: {
                default_activity_type_id: this.voip.callActivityTypeId,
                default_res_id: contact.id,
                default_res_model: "res.partner",
            },
        });
    }

    onClickBack() {
        if (this.props.state.showMore) {
            this.props.state.showMore = false;
        } else if (this.props.onClickBack) {
            this.props.onClickBack();
        }
    }

    onClickBackspace() {
        const { selectionStart, selectionEnd, value } = this.inputRef.el;
        const cursorPosition =
            selectionStart === selectionEnd && selectionStart !== 0
                ? selectionStart - 1
                : selectionStart;
        if (selectionEnd !== 0) {
            this.props.state.input.value =
                value.slice(0, cursorPosition) + value.slice(selectionEnd);
            this.updateCountryCode();
        }
        this.selection.moveCursor(cursorPosition);
        this.props.state.input.focus = true;
        this.onInputSearchBar();
    }

    onClickCall(contact) {
        this.userAgent.makeCall({ partner: contact, phone_number: contact.phone });
    }

    onClickContact(contact) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: contact.id,
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
        });
    }

    onClickFirstResult(contact) {
        this.props.onClickFirstResult(contact);
    }

    /** @param {string} key */
    onClickKey(key) {
        if (this.props.dtmf) {
            this.userAgent.activeSession?.sipSession?.sessionDescriptionHandler.sendDtmf(key);
            this.props.state.input.value += key;
        } else {
            const { selectionStart, selectionEnd, value } = this.inputRef.el;
            this.props.state.input.value =
                value.slice(0, selectionStart) + key + value.slice(selectionEnd);
            this.selection.moveCursor(selectionStart + 1);
            this.props.state.input.focus = true;
            this.onInputSearchBar();
        }
    }

    onClickShowMore() {
        this.props.state.showMore = true;
    }

    onInputSearchBar(ev) {
        const searchTerms = this.props.state.input.value.trim();
        if (!searchTerms) {
            return;
        }
        const isT9Code = [...searchTerms].every((letter) => letter in T9_MAPPING);
        this.updateCountryCode();
        this.voip.fetchContacts(searchTerms, 0, 30, isT9Code);
    }

    /** @param {KeyboardEvent} ev */
    onKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        const inputValue = this.props.state.input.value.trim();
        if (!inputValue) {
            return;
        }
        if (this.userAgent.activeSession?.sipSession && this.props.onClickTransferPhone) {
            this.props.onClickTransferPhone();
        } else {
            this.userAgent.makeCall({ phone_number: inputValue });
        }
    }

    async updateCountryCode() {
        const phoneNumber = this.props.state.input.value.trim();
        // avoid making a request if the country code is already up to date
        if (this.phoneNumberStartsWithCountryCode) {
            return;
        }
        if (!phoneNumber.startsWith("00") && !phoneNumber.startsWith("+")) {
            return;
        }
        const { countryId, storeData } = await rpc("/voip/get_country_store", {
            phone_number: phoneNumber,
        });
        this.voip.store.insert(storeData);
        this.props.state.input.country = this.voip.store["res.country"].get(countryId) || null;
    }
}

/**
 * @param {string} str
 * @param {string} substr
 * @returns {ReturnType<markup>|string}
 */
export function highlightMatch(str, substr) {
    const { start, end, match } = normalizedMatch(str, substr);
    if (!match) {
        return "";
    }
    return htmlJoin([
        str.slice(0, start),
        markup`<span class="o-voip-highlighted-letter fw-bolder">${match}</span>`,
        str.slice(end),
    ]);
}

function highlightT9Match(name, t9) {
    t9 = [...t9].reverse();
    const nameAsArr = [...name];
    let matchEnd = 0;
    for (matchEnd = 0; matchEnd < nameAsArr.length; ++matchEnd) {
        if (t9.length < 1) {
            break;
        }
        const normalized = normalize(nameAsArr[matchEnd]).toUpperCase();
        // extra loop, in case normalizing generates more letters
        for (const char of normalized) {
            if (t9.length === 0) {
                return "";
            }
            const possibleLetters = T9_MAPPING[t9.pop()];
            if (!possibleLetters.includes(char)) {
                return "";
            }
        }
    }
    if (t9.length !== 0) {
        return "";
    }
    return htmlJoin([
        markup`<span class="o-voip-highlighted-letter fw-bolder">`,
        ...nameAsArr.slice(0, matchEnd),
        markup`</span>`,
        ...nameAsArr.slice(matchEnd),
    ]);
}
