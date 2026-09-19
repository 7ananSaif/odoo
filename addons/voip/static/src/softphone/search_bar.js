import { Component, useEffect, useRef } from "@odoo/owl";

import { isCurrentFocusEditable } from "@voip/utils/utils";

import { useService } from "@web/core/utils/hooks";

/**
 * Search bar component used in softphone tabs to filter entries.
 */
export class SearchBar extends Component {
    static template = "voip.SearchBar";
    static props = {
        state: { type: Object },
        onInputSearch: { type: Function },
        onClickBack: { type: Function, optional: true },
        slots: { type: Object, optional: true },
    };

    setup() {
        this.voip = useService("voip");
        this.softphone = this.voip.softphone;
        this.searchInput = useRef("searchInput");
        useEffect(
            (shouldFocus) => {
                if (shouldFocus) {
                    if (this.searchInput.el && !this.voip.error && !isCurrentFocusEditable()) {
                        this.searchInput.el.focus();
                    }
                    this.softphone.shouldFocus = false;
                }
            },
            () => [this.softphone.shouldFocus]
        );
    }

    /**
     * When an RPC is pending, the search icon is replaced with a spinner.
     *
     * @returns {string}
     */
    get searchBarIcon() {
        if (this.voip.hasPendingRequest) {
            return "fa fa-spin fa-circle-o-notch";
        }
        return "oi oi-search";
    }
}
