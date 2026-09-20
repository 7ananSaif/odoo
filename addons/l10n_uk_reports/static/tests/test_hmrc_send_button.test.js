import { describe, expect, test } from "@odoo/hoot";
import { SendHmrcButton } from "@l10n_uk_reports/components/send_hmrc/send_hmrc";


describe("SendHmrcButton - retrieveClientInfo", () => {

    test("retrieveClientInfo function works correctly", async () => {
        const mockProps = {
            record: {
                data: {
                    obligation_id: {id: 1, clientData: "Test Obligation"},
                    hmrc_gov_client_device_id: "test-device-123"
                }
            }
        };

        const component = new SendHmrcButton();
        component.props = mockProps;

        component.orm = {
            call: (model, method, args) => {
                expect(model).toBe('l10n_uk.vat.obligation');
                expect(method).toBe('action_submit_vat_return');
                expect(args[0]).toBe(1);
                return Promise.resolve(true);
            }
        };

        component.actionService = {
            doAction: (action) => {
                expect(action.type).toBe('ir.actions.act_window_close');
            }
        };

        component.env = {
            services: {
                ui: {
                    block: () => console.log("UI blocked"),
                    unblock: () => console.log("UI unblocked")
                }
            }
        };

        localStorage.removeItem('hmrc_gov_client_device_id');

        await component.retrieveClientInfo();

        localStorage.removeItem('hmrc_gov_client_device_id');
    });
});
