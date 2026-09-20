import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { user } from "@web/core/user";

const serviceRegistry = registry.category("services");

export function systemColorScheme() {
    return browser.matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light";
}

export function currentColorScheme() {
    return cookie.get("color_scheme");
}

export const blockingWebClient = Promise.withResolvers();

export const colorSchemeService = {
    async start() {
        let newColorScheme = systemColorScheme();
        if (["light", "dark"].includes(user.settings.color_scheme)) {
            newColorScheme = user.settings.color_scheme;
        }
        const current = currentColorScheme();
        if (newColorScheme !== current) {
            cookie.set("color_scheme", newColorScheme);
            if (current || (!current && newColorScheme === "dark")) {
                this.reload();
                await blockingWebClient.promise; // block WebClient rendering to avoid flickering
            }
        }
        return {
            get systemColorScheme() {
                return systemColorScheme();
            },
            get currentColorScheme() {
                return currentColorScheme();
            },
            get userColorScheme() {
                return user.settings.color_scheme;
            },
        };
    },
    reload() {
        browser.location.reload();
    },
};
serviceRegistry.add("color_scheme", colorSchemeService);
