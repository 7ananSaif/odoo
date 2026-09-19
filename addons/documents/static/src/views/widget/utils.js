export const DESTINATION_MAX_LENGTH = 15;

// Copied from web/static/lib/hoot/hoot_utils.js
const ELLIPSIS = "…";
const MAX_HUMAN_READABLE_SIZE = 80;
/**
 * @param {string} value
 * @param {number} [length=MAX_HUMAN_READABLE_SIZE]
 */
export const truncate = (value, length = MAX_HUMAN_READABLE_SIZE) => {
    const strValue = String(value);
    return strValue.length <= length ? strValue : strValue.slice(0, length) + ELLIPSIS;
};
