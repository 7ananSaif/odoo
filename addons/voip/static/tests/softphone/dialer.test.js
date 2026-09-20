import { describe, expect, test } from "@odoo/hoot";

import { highlightMatch } from "@voip/softphone/keypad";

describe.current.tags("headless");

test("highlightMatch", () => {
    const match = highlightMatch("Œdipe Roi", "oed");
    expect(match.valueOf()).toBe(
        `<span class="o-voip-highlighted-letter fw-bolder">Œd</span>ipe Roi`
    );
});
