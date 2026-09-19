import { BaseOptionComponent } from "@html_builder/core/utils";

export class AILivechatOption extends BaseOptionComponent {
    static template = "ai_website_livechat.AILivechatOption";
    static selector = ".s_ai_livechat";
    static components = { ...BaseOptionComponent };
}
