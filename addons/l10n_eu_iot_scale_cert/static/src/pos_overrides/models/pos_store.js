import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { CertifiedScaleScreen } from "../components/scale_screen/certified_scale_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(PosStore.prototype, {
    async processServerData() {
        await super.processServerData(...arguments);

        this.isScaleIconVisible =
            this.config.iface_electronic_scale &&
            this.config._is_eu_country &&
            this.models["product.product"].some((product) => product.to_weight);

        // TODO: The POS is only certified in 18.0, so we will disable the certification messages. Once a new version is certified, this line should be removed.
        this.isScaleIconVisible = false;

        this.config.isCertified = this.isCertified;
        this.config.showCertificationWarning = this.isScaleIconVisible && !this.isCertified;
    },

    get decimalAccuracy() {
        return this.models["decimal.precision"].find((dp) => dp.name === "Product Unit");
    },

    get certificationErrors() {
        const errors = [];
        if (this.config._scale_checksum !== this.config._scale_checksum_expected) {
            errors.push(
                _t("Checksum does not match, the code has been modified and is no longer certified")
            );
        }
        if (this.decimalAccuracy.digits < 3) {
            errors.push(_t("Decimal accuracy is less than 3 decimal places"));
        }
        return errors;
    },

    get isCertified() {
        return this.certificationErrors.length === 0;
    },

    async weighProduct() {
        if (this.isCertified && this.scale.product.unitOfMeasureId !== this.config._kg_uom_id) {
            this.dialog.add(AlertDialog, {
                title: _t("Unable to weigh product"),
                body: _t("The unit of measure must be set to kg to weigh in a certified POS."),
            });
            this.scale.reset();
            return 0;
        }
        const result = await makeAwaitable(this.env.services.dialog, CertifiedScaleScreen);
        // Returning 0 instead of null stops the POS still adding
        // an orderline in case of error (not desired behaviour when certified)
        return result ?? 0;
    },
});
