import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { EventBus, useSubEnv } from "@odoo/owl";

export class SignSendRequestController extends formView.Controller {
    static props = {
        ...formView.Controller.props,
        fullComposerBus: { type: EventBus, optional: true },
    };
    static defaultProps = { fullComposerBus: new EventBus() };
    setup() {
        super.setup();
        useSubEnv({
            fullComposerBus: this.props.fullComposerBus,
        });
    }
}

registry.category("views").add("sign_send_request_form", {
    ...formView,
    Controller: SignSendRequestController,
});
