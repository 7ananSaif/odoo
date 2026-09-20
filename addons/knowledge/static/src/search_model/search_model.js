import { SearchModel } from "@web/search/search_model";

export const KnowledgeSearchModelMixin = (T) => class extends T {
    setup(services, args) {
        this.saveEmbeddedViewFavoriteFilter = args.saveEmbeddedViewFavoriteFilter;
        this.deleteEmbeddedViewFavoriteFilter = args.deleteEmbeddedViewFavoriteFilter;
        super.setup(services, args);
    }

    /**
     * Favorites for embedded views
     * @override
     */
    async load(config) {
        await super.load(config);
        if (config.state && !this.isStateCompleteForEmbeddedView) {
            // If the config contains an imported state that is not directly
            // coming from a view that was embedded in Knowledge, the favorite
            // filters have to be loaded, since they come from the
            // `data-embedded-props` attribute of the anchor for the
            // EmbeddedViewComponent. Otherwise, those are already specified in
            // the state and they should not be duplicated.
            let defaultFavoriteId = null;
            const activateFavorite = "activateFavorite" in config ? config.activateFavorite : true;
            if (activateFavorite) {
                defaultFavoriteId = this._createGroupOfFavorites(this.irFilters || []);
                if (defaultFavoriteId) {
                    // activate default search items (populate this.query)
                    this._activateDefaultSearchItems(defaultFavoriteId);
                }
            }
        }
    }

    /**
     * Save in embedded view arch instead of creating a record
     * @override
     */
    async _createIrFilters(irFilter) {
        this.saveEmbeddedViewFavoriteFilter(irFilter);
        return null;
    }

    /**
     * The super method handles real ir.filters records from the database. In an
     * Embedded View, favorites are only stored as html metadata, they do not
     * relate to a database record, so there is nothing to reconciliate.
     * @override
     */
    _reconciliateFavorites() {}

    deleteFavorite(favoriteId) {
        const searchItem = this.searchItems[favoriteId];
        if (searchItem.type !== "favorite") {
            return;
        }
        this._deleteIrFilters(searchItem);
        const index = this.query.findIndex((queryElem) => queryElem.searchItemId === favoriteId);
        delete this.searchItems[favoriteId];
        if (index >= 0) {
            this.query.splice(index, 1);
        }
        this._notify();
    }

    /**
     * Delete from the embedded view embedded state
     */
    _deleteIrFilters(searchItem) {
        this.deleteEmbeddedViewFavoriteFilter(searchItem);
    }

    /**
     * @override
     * @returns {Object}
     */
    exportState() {
        const state = super.exportState();
        state.isStateCompleteForEmbeddedView = true;
        return state;
    }

    /**
     * @override
     */
    _importState(state) {
        super._importState(state);
        this.isStateCompleteForEmbeddedView = state.isStateCompleteForEmbeddedView;
    }
};

export class KnowledgeSearchModel extends KnowledgeSearchModelMixin(SearchModel) {}
