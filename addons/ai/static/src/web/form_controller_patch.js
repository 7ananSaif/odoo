import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { useEffect } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
        const openAiChat = (ev) => this.openAiChat(ev.detail.origin);
        useEffect(
            () => {
                this.env.bus.addEventListener("AI:OPEN_AI_CHAT", openAiChat);
                return () => this.env.bus.removeEventListener("AI:OPEN_AI_CHAT", openAiChat);
            },
            () => []
        );
    },

    async openAiChat(callerComponentName) {
        // save to allow to get messages from backend
        if (!this.mailStore || !(await this.model.root.save())) {
            return;
        }
        this.aiChatLauncher.launchAIChat({
            callerComponentName,
            channelTitle: this.displayName(),
            recordModel: this.model.root.resModel,
            recordId: this.model.root.resId,
            originalRecordData: this.model.root.data,
            originalRecordFields: this.model.root.fields,
            aiChatSourceId: this.model.root.resId,
        });
    },
});
