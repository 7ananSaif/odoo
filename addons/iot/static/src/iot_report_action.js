import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser"
import {
    IOT_REPORT_PREFERENCE_LOCAL_STORAGE_KEY,
    setReportIdInBrowserLocalStorage,
} from "./client_action/delete_local_storage";
import { uuid } from "@web/core/utils/strings";

/**
 * Method to print the report with the selected devices
 *
 * @param env Environment
 * @param args Arguments to render the report (report_id, active_record_ids, report_data)
 * @param selected_device_ids Selected device ids (those stored in local storage)
 * @returns {Promise<void>}
 */
export async function printReport(env, args, selected_device_ids) {
    const orm = env.services.orm;
    const notification = env.services.notification;
    const iotHttp = env.services.iot_http;

    const [report_id, active_record_ids, report_data] = args;
    const jobs = await orm.call(
        "ir.actions.report", "render_document",
        [report_id, selected_device_ids, active_record_ids, report_data]
    );

    for (const job of jobs) {
        const { iotBoxId, deviceIdentifier, deviceName, document } = job;
        const removeSendingNotification = notification.add(_t("Sending document to printer %s...", deviceName), {
            type: "info",
            sticky: true,
        });

        await iotHttp.action(iotBoxId, deviceIdentifier, { document, print_id: uuid() }, () => {
            removeSendingNotification?.();
            notification.add(_t("Started printing operation on printer %s...", deviceName), { type: "success" });
        });
    }
}

export async function getSelectedPrintersForReport(reportId, env) {
    const { orm, action, ui } = env.services;
    const deviceSettingsByReportId = JSON.parse(browser.localStorage.getItem(IOT_REPORT_PREFERENCE_LOCAL_STORAGE_KEY));
    const deviceSettings = deviceSettingsByReportId?.[reportId];

    if (deviceSettings && deviceSettings.skipDialog) {
        return deviceSettings.selectedDevices;
    }

    // Open IoT devices selection wizard
    const openDeviceSelectionWizard = await orm.call("ir.actions.report", "get_action_wizard", [reportId, deviceSettings?.selectedDevices]);
    await action.doAction(openDeviceSelectionWizard);

    // If the UI is currently blocked, we need to temporarily unblock it or the user won't be able to select the printer
    const uiWasBlocked = ui.isBlocked;
    if (uiWasBlocked) {
        ui.unblock();
    }

    // Wait for the popup to be closed and a printer selected
    return new Promise((resolve) => {
        const onPrinterSelected = (event) => {
            if (event.detail.reportId === reportId) {
                const newDeviceSettings = event.detail.deviceSettings;
                if (newDeviceSettings) {
                    setReportIdInBrowserLocalStorage(reportId, newDeviceSettings);
                }
                resolve(newDeviceSettings ? newDeviceSettings.selectedDevices : null);
                env.bus.removeEventListener("printer-selected", onPrinterSelected);
                if (uiWasBlocked) {
                    ui.block();
                }
            }
        };
        env.bus.addEventListener("printer-selected", onPrinterSelected);
    });
}

async function iotReportActionHandler(action, options, env) {
    if (action.device_ids && action.device_ids.length) {
        action.data ??= {};
        const args = [action.id, action.context.active_ids, action.data];
        const reportId = action.id;
        const printerIds = await getSelectedPrintersForReport(reportId, env);

        if (!printerIds) {
            // If the user does not select any printer, fall back to normal printing
            return false;
        }

        env.services.ui.block();
        // Try longpolling then websocket
        await printReport(env, args, printerIds);
        env.services.ui.unblock();

        options.onClose?.();
        return true;
    }
}

registry
    .category("ir.actions.report handlers")
    .add("iot_report_action_handler", iotReportActionHandler);
