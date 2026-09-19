const SELECTOR = `[data-embedded="view"],[data-embedded="viewLink"]`;

/**
 * This migration handles the `user_id` field being replaced by `user_ids`.
 *
 * In the new implementation, to have a favorite filter in the
 * `FAVORITE_SHARED_GROUP` of the SearchModel (as opposed to the
 * `FAVORITE_PRIVATE_GROUP`), `user_ids` must either be empty or have more than
 * one value. In Knowledge, all favorites of an embedded view are visible by
 * everyone, so it makes more sense to use `FAVORITE_SHARED_GROUP`, and use
 * an empty list as `user_ids` (as a reminder, embedded view favorites are
 * not real `ir.filters` records, they are stored as html meta data in an
 * article body, so they are not directly related to any user anymore).
 *
 * @param {HTMLElement} container
 */
export function migrate(container) {
    for (const host of container.querySelectorAll(SELECTOR)) {
        migrateEmbeddedViewIrFilters(host);
    }
}

function migrateEmbeddedViewIrFilters(host) {
    if (!host.dataset.embeddedProps) {
        return;
    }
    const embeddedProps = JSON.parse(host.dataset.embeddedProps);
    if (embeddedProps.viewProps?.context?.knowledge_search_model_state) {
        migrateSearchModelState(embeddedProps);
    }
    if (embeddedProps.viewProps?.favoriteFilters) {
        migrateFavoriteFilters(embeddedProps);
    }
    host.dataset.embeddedProps = JSON.stringify(embeddedProps);
}

function migrateSearchModelState(embeddedProps) {
    const state = JSON.parse(embeddedProps.viewProps.context.knowledge_search_model_state);
    if (!state.searchItems) {
        return;
    }
    for (const searchItem of Object.values(state.searchItems)) {
        if (searchItem.type !== "favorite") {
            continue;
        }
        delete searchItem.userId;
        searchItem.userIds = [];
    }
    embeddedProps.viewProps.context.knowledge_search_model_state = JSON.stringify(state);
}

function migrateFavoriteFilters(embeddedProps) {
    const favoriteFilters = embeddedProps.viewProps.favoriteFilters;
    for (const favorite of Object.values(favoriteFilters)) {
        delete favorite.user_id;
        favorite.user_ids = [];
    }
}
