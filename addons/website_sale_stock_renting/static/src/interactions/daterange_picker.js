import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';
import { DaterangePicker } from '@website_sale_renting/interactions/daterange_picker';

patch(DaterangePicker.prototype, {
    setup() {
        super.setup();
        patchDynamicContent(this.dynamicContent, {
            _root: {
                't-on-change_product_id': this.onChangeProductId.bind(this),
            },
        });
    },

    /**
     * Override to get the renting product availabilities.
     */
    async willStart() {
        await this.waitFor(super.willStart());
        await this._updateRentingProductAvailabilities();
    },

    /**
     * Update the availabilities when the product changes.
     *
     * @param {CustomEvent} event
     */
    async onChangeProductId(event) {
        const { productId } = event.detail;
        if (this.productId !== productId) {
            this.productId = productId;
            await this._updateRentingProductAvailabilities();
        }
    },
});
