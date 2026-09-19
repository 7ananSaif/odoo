import { activityView } from "@mail/views/web/activity/activity_view";
import { SignActivityController } from "./sign_activity_controller";
import { registry } from "@web/core/registry";

export const SignActivityView = {
    ...activityView,
    Controller: SignActivityController,
};

registry.category("views").add("sign_activity", SignActivityView);
