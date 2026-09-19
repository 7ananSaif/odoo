import { useVisible } from "@mail/utils/common/hooks";

import { Component } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";

/**
 * Generic component that defines the general structure of a softphone tab.
 */
export class Tab extends Component {
    static defaultProps = {
        extraClass: "",
        getSectionStyle: (item) => "",
        noEntriesMessage: _t("Nothing to see here 😔"),
        onTabEnd: () => {},
        sectionIcon: "",
    };
    static props = {
        extraClass: { type: String, optional: true },
        /**
         * Function that computes the additional classes to be applied to a
         * section name. It takes the first item of the section as an argument.
         */
        getSectionStyle: { type: Function, optional: true },
        itemsBySection: Map,
        /**
         * Message displayed when there are no entries in the tab.
         */
        noEntriesMessage: { type: String, optional: true },
        noSearchResultsMessage: { type: String, optional: true },
        onClickBack: { type: Function, optional: true },
        /**
         * Function to be called each time the user scrolls to the end of the
         * tab. Useful to implement "load more" feature.
         */
        onTabEnd: { type: Function, optional: true },
        sectionIcon: { type: String, optional: true },
        slots: Object,
        state: Object,
    };
    static template = "voip.Tab";

    setup() {
        useVisible("end-of-tab", (isVisible) => {
            if (isVisible) {
                this.props.onTabEnd();
            }
        });
    }
}

import { ActionButton } from "@voip/softphone/action_button";
import { NoSearchResults } from "@voip/softphone/no_search_results";
import { SearchBar } from "@voip/softphone/search_bar";
import { TabEntry } from "@voip/softphone/tab_entry";

export const tabComponents = { ActionButton, NoSearchResults, SearchBar, Tab, TabEntry };
