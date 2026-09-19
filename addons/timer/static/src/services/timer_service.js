import { registry } from "@web/core/registry";
import { TimerReactive } from "../models/timer_reactive";

export const timerService = {
    async: ["getServerOffset"],
    start(env) {
        let serverOffset = null;
        let timer;
        return {
            get timer() {
                return timer;
            },
            createTimer() {
                if (!timer) {
                    timer = new TimerReactive(env);
                }
                return timer;
            },
            async getServerOffset() {
                if (serverOffset == null) {
                    const serverTime = await timer.getServerTime();
                    timer.computeOffset(serverTime);
                    serverOffset = timer.serverOffset;
                }
                return serverOffset;
            },
        };
    },
};

registry.category("services").add("timer", timerService);
