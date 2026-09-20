import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { cookie } from "@web/core/browser/cookie";
import { browser } from "@web/core/browser/browser";

patch(Navbar.prototype, {
    get colorScheme() {
        return cookie.get("pos_color_scheme") || "light";
    },
    toggleColorScheme() {
        cookie.set("pos_color_scheme", this.colorScheme === "dark" ? "light" : "dark");
        browser.location.reload();
    },
});
