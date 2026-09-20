import { Component } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";

/**
 * Message displayed in a softphone tab when there are no search results.
 */
export class NoSearchResults extends Component {
    static props = {
        actionCallback: Function,
        actionMessage: String,
        icon: String,
        noResultsMessage: String,
    };
    static template = "voip.NoSearchResults";

    setup() {
        this.action = useService("action");
    }
}
