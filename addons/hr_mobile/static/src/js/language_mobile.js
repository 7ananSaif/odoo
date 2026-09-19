import { patch } from "@web/core/utils/patch";
import { updateAccountOnMobileDevice } from "@web_mobile/js/core/mixins";
import { HrUserPreferencesController } from "@hr/views/preferences_form_view";

patch(HrUserPreferencesController.prototype, {
    async onRecordSaved(record) {
        await updateAccountOnMobileDevice();
        return await super.onRecordSaved(...arguments);
    },
});
