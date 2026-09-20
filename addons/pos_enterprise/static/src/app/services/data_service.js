import { PosData } from "@point_of_sale/app/services/data_service";
import { patch } from "@web/core/utils/patch";

export const unpatchPrepDataService = patch(PosData.prototype, {
    async loadInitialData() {
        const pdisId = odoo.preparation_display.id;
        return await this.orm.call("pos.prep.display", "load_preparation_data", [parseInt(pdisId)]);
    },
    async loadFieldsAndRelations() {
        const pdisId = odoo.preparation_display.id;
        return await this.orm.call("pos.prep.display", "load_data_params", [parseInt(pdisId)]);
    },
    async initData(hard = false, limit = true) {
        const data = await this.loadInitialData(hard, limit);

        this.models.loadConnectedData(data, this.modelToLoad);
    },
    async initializeDeviceIdentifier() {
        return false;
    },
    initializeWebsocket() {
        return false;
    },
    initIndexedDB() {
        return false;
    },
    initListeners() {
        return false;
    },
    synchronizeLocalDataInIndexedDB() {
        return true;
    },
    async getCachedServerDataFromIndexedDB() {
        return {};
    },
    async getLocalDataFromIndexedDB() {
        return {};
    },
    async missingRecursive(recordMap) {
        return recordMap;
    },
});
