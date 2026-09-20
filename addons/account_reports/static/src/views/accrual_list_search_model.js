import { useSubEnv } from "@odoo/owl";
import { SearchModel } from "@web/search/search_model";

export class AccrualListSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        this.accrualContext = {};
        useSubEnv({ accrualContext: this.accrualContext });
    }

    _getContext() {
        const context = super._getContext();
        Object.assign(context, this.accrualContext);
        return context;
    }
}
