import { stateToUrl, urlToState } from "./router_utils";
import { browser } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { patch } from "@web/core/utils/patch";

patch(router, {
    stateToUrl,
    urlToState,
});

// Since the patch for `stateToUrl` and `urlToState` is executed
// after the router state was already initialized, it has to be replaced.
router.replaceState(router.urlToState(new URL(browser.location)));
