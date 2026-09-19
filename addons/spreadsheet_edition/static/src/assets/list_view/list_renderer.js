import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";

patch(ListRenderer.prototype, {
    /**
     * @override
     */
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
        this.actionService = useService("action");
    },
});
