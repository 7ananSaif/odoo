import { describe, expect, test } from "@odoo/hoot";

import { matchPhoneNumber } from "@voip/utils/utils";

describe.current.tags("headless");

describe("matchPhoneNumber", () => {
    test("phone number with space, dash, slash and parentheses", () => {
        const { before, match, after } = matchPhoneNumber("+1 (234) 567-89/00", "234567890");
        expect(match).toBe("234) 567-89/0");
        expect(before).toBe("+1 (");
        expect(after).toBe("0");
    });

    test("phone number with plus prefix", () => {
        const { before, match, after } = matchPhoneNumber("+1 (234) 567-89/00", "+1234567890");
        expect(match).toBe("+1 (234) 567-89/0");
        expect(before).toBe("");
        expect(after).toBe("0");
    });

    test("phone number with asterisk, sharp, semicolon and comma", () => {
        const { before, match, after } = matchPhoneNumber("123*4#5;6,7890", "34#56,7");
        expect(match).toBe("3*4#5;6,7");
        expect(before).toBe("12");
        expect(after).toBe("890");
    });

    test("phone number without asterisk won't be matched against search term with asterisk", () => {
        const result = matchPhoneNumber("123-456-7890", "456*78");
        expect(result).toBe(null);
    });
});
