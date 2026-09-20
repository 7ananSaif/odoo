import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class TimerGeolocationService {
    constructor(env, services) {
        this.notification = services["notification"];
    }

    async getPosition() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
            });
        });
    }

    async getGeoLocation() {
        try {
            const position = await this.getPosition();
            return {
                success: true,
                longitude: position.coords.longitude,
                latitude: position.coords.latitude,
            };
        } catch (err) {
            return {
                success: false,
                message: _t("Location error: %s", err.message),
            };
        }
    }
}

export const timerGeolocationService = {
    dependencies: ["notification"],
    start(env, services) {
        return new TimerGeolocationService(env, services);
    },
};

registry.category("services").add("timer_geolocation", timerGeolocationService);
