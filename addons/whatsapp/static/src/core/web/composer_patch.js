import { Composer } from "@mail/core/common/composer";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
    },
    get isRevivingWhatsapp() {
        return this.action.id === "revive-whatsapp-conversation";
    },
});
