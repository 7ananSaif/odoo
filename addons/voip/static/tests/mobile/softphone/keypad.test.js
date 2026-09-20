import { describe, expect, test } from "@odoo/hoot";
import { mockUserAgent } from "@odoo/hoot-mock";
import { click, contains, insertText, start } from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

describe.current.tags("mobile");
setupVoipTests();

test.tags("focus required");
test("Clicking a keypad key *should* focus the input on mobile, to see the cursor", async () => {
    await start();
    mockUserAgent("android");
    await click(".o_menu_systray button:has(> .oi-voip)");
    await click(".o-voip-Softphone nav button:has(> .oi-numpad)");
    await click(".o-voip-Keypad-digitBtn:has(> span:text('2'))");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    expect(document.activeElement).toBe(input);
});

test.tags("focus required");
test("Cursor position is correct after backspace in the middle of a number", async () => {
    mockUserAgent("android");
    await start();
    await click(".o_menu_systray button:has(> .oi-voip)");
    await click(".o-voip-Softphone nav button:has(> .oi-numpad)");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123456");
    const inputEl = document.querySelector(".o-voip-Keypad-searchBar input");
    inputEl.setSelectionRange(3, 3);

    // TODO this would not be needed if `useSelection.moveCursor` would actually
    // move the cursor in mobile also. To change in master?
    await new Promise(setTimeout);

    await click(".o-voip-Keypad-backspace");
    await contains(".o-voip-Keypad-searchBar input:value(12456)");
    expect(inputEl.selectionStart).toBe(2);
    expect(inputEl.selectionEnd).toBe(2);
});

test.tags("focus required");
test("Cursor position is correct after inserting a number in the middle of a number", async () => {
    mockUserAgent("android");
    await start();
    await click(".o_menu_systray button:has(> .oi-voip)");
    await click(".o-voip-Softphone nav button:has(> .oi-numpad)");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123456");
    const inputEl = document.querySelector(".o-voip-Keypad-searchBar input");
    inputEl.setSelectionRange(3, 3);

    // TODO this would not be needed if `useSelection.moveCursor` would actually
    // move the cursor in mobile also. To change in master?
    await new Promise(setTimeout);

    await click(".o-voip-Keypad-digitBtn:has(> span:text('8'))");
    await contains(".o-voip-Keypad-searchBar input:value(1238456)");
    expect(inputEl.selectionStart).toBe(4);
    expect(inputEl.selectionEnd).toBe(4);
});
