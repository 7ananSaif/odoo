import { FDM_MESSAGES } from "@iot/network_utils/iot_http_service";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

export class BlackboxError extends Error {
    constructor(code = "disconnected", message = null, retry = undefined) {
        super(message);
        this.name = "BLACKBOX_ERROR";
        this.type = "blackbox";
        this.code = code;
        this.message = FDM_MESSAGES[code?.toString()?.substring(0, 3)] || message;
        this.retry = retry;

        logPosMessage("FDM", "BlackboxError", `${this.code}: ${this.message}`);
    }
}
