import { CustomFavoriteItem } from "@web/search/custom_favorite_item/custom_favorite_item";
import { patch } from "@web/core/utils/patch";

patch(CustomFavoriteItem.prototype, {
    isKnowledgeEmbeddedView() {
        return (
            this.env.searchModel &&
            this.env.searchModel.context &&
            this.env.searchModel.context.knowledgeEmbeddedViewId
        );
    },

    async saveFavorite(ev) {
        return super.saveFavorite(ev, this.isKnowledgeEmbeddedView());
    },
});
