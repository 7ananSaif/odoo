import { mailModels } from "@mail/../tests/mail_test_helpers";

export class ResUsers extends mailModels.ResUsers {
    /**
     * @override
     */
    _init_store_data(store) {
        super._init_store_data(...arguments);
        store.add({ hasDocumentsUserGroup: true });
    }
}
