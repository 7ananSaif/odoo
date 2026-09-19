import { patch } from "@web/core/utils/patch";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { isFiscalPrinterConfigured } from "./helpers/utils";

patch(ProductTemplate.prototype, {
    // EXTENDS 'point_of_sale'
    prepareProductBaseLineForTaxesComputationExtraValues(
        price,
        pricelist = false,
        fiscalPosition = false
    ) {
        const extraValues = super.prepareProductBaseLineForTaxesComputationExtraValues(
            price,
            pricelist,
            fiscalPosition
        );
        const config = this.models["pos.config"].getFirst();
        extraValues.l10n_it_epson_printer = isFiscalPrinterConfigured(config);
        return extraValues;
    },
});
