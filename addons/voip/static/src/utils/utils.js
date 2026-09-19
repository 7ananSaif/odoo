import { normalize } from "@web/core/l10n/utils";
import { escapeRegExp } from "@web/core/utils/strings";

/**
 * Removes whitespaces, dashes, slashes and periods from a phone number.
 *
 * @param {string} phoneNumber
 * @returns {string}
 */
export function cleanPhoneNumber(phoneNumber) {
    // U+00AD is the “soft hyphen” character
    return phoneNumber.replace(/[-()\s/.\u00AD]/g, "");
}

const editableInputTypes = new Set([
    "date",
    "datetime-local",
    "email",
    "month",
    "number",
    "password",
    "search",
    "tel",
    "text",
    "time",
    "url",
    "week",
]);

/**
 * Determines whether the currently focused element is editable. This is useful
 * for preventing auto-focus mechanisms when the user is already typing
 * elsewhere.
 *
 * @returns {boolean}
 */
export function isCurrentFocusEditable() {
    const el = document.activeElement;
    if (!el) {
        return false;
    }
    if (el.isContentEditable) {
        return true;
    }
    const tag = el.tagName.toLowerCase();
    if (tag === "textarea") {
        return true;
    }
    if (tag === "input") {
        const inputType = el.getAttribute("type")?.toLowerCase() || "text";
        return editableInputTypes.has(inputType);
    }
    return false;
}

export function isSubstring(targetString, substring) {
    if (!targetString) {
        return false;
    }
    return normalize(targetString).includes(normalize(substring));
}

/**
 * Matches a target number against a search term and returns a three-part result
 * for highlighting.
 *
 * @param {string} targetNumber - The full phone number to search within.
 * @param {string} searchTerms - The user's original search term.
 * @returns {{before: string, match: string, after: string} | null}
 * An object with the following properties if a match is found, otherwise null:
 * - `before`: The substring of `targetNumber` that comes *before* the match.
 * - `match`: The actual substring of `targetNumber` that *matched* the regex.
 * - `after`: The substring of `targetNumber` that comes *after* the match.
 */
export function matchPhoneNumber(targetNumber, searchTerms) {
    if (/[a-zA-Z]/.test(searchTerms)) {
        return null;
    }
    const r = String.raw;
    const hasPlusPrefix = searchTerms.trim().startsWith("+");
    const sanitizedSearchTerms = searchTerms.replace(/[^0-9*#;,]/g, "");
    let regexString = Array.from(sanitizedSearchTerms, escapeRegExp).join(r`\D*`);
    if (!regexString && !hasPlusPrefix) {
        return null;
    }
    if (hasPlusPrefix) {
        regexString = r`\+\D*${regexString}`;
    }
    const regex = new RegExp(`(^.*?)(${regexString})(.*?$)`, "i");
    const [, before, match, after] = targetNumber.match(regex) ?? [];
    if (match) {
        return { before, match, after };
    }
    return null;
}
