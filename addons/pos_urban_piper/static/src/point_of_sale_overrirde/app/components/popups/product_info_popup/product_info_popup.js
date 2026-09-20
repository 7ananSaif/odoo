import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ProductInfoPopup } from "@point_of_sale/app/components/popups/product_info_popup/product_info_popup";

patch(ProductInfoPopup.prototype, {
    get product() {
        return this.props.productTemplate;
    },
    get availableForFoodDelivery() {
        return this.product.isAvailableForFoodDelivery(this.pos.config.id);
    },
    get showFoodDeliveryAvailability() {
        return (
            this.pos.config.module_pos_urban_piper &&
            this.allowProductEdition &&
            this.product._synced_on_urbanpiper
        );
    },
    async switchFoodDeliveryAvailability() {
        this.pos.env.services.ui.block();
        try {
            const response = await this.pos.data.call(
                "product.template",
                "toggle_product_food_delivery_availability",
                [this.product.id, this.pos.config.id],
                {
                    context: {
                        from_pos_ui: true,
                    },
                }
            );
            if (response.status !== "success") {
                this.pos.notification.add(response.error, { type: "danger" });
            }
        } catch {
            this.pos.notification.add(_t("Failed to update food delivery availability."), {
                type: "danger",
            });
        }
        this.pos.env.services.ui.unblock();
    },
});
