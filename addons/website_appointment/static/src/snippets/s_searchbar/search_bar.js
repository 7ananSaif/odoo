import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@website/snippets/s_searchbar/search_bar";

patch(SearchBar.prototype, {
    /**
     * Allows to keep the invite token and the filters in the URL
     * parameters after clicking on the search bar suggestions.
     *
     * @override
     */
    render(res) {
        if (res && this.searchType === 'appointments' && res.parts.website_url) {
            res.results.forEach(result => {
                result.website_url = `${result.website_url}${location.search}`;
            })
        }
        super.render(...arguments);
    },
});
