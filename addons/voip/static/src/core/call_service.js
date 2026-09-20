import { registry } from "@web/core/registry";

export class CallService {
    missedCalls = 0;

    constructor(env, services) {
        this.env = env;
        this.orm = services.orm;
        this.store = services["mail.store"];
    }

    async abort(call) {
        this.store.insert(await this.orm.call("voip.call", "abort_call", [[call.id]]));
    }

    async create(data) {
        const { activity, partner } = data;
        delete data.activity;
        delete data.partner;
        data.partner_id = partner?.id;
        const {
            ids: [id],
            store_data,
        } = await this.orm.call("voip.call", "create_and_format", [], data);
        this.store.insert(store_data);
        const call = this.store["voip.call"].insert(id);
        if (activity) {
            call.activity = activity;
        }
        if (!call.partner_id) {
            this.orm.call("voip.call", "get_contact_info", [[call.id]]).then((data) => {
                if (data) {
                    this.store.insert(data);
                }
            });
        }
        return call;
    }

    async end(call, { activityDone = true } = {}) {
        let data;
        if (call.activity && activityDone) {
            data = await this.orm.call("voip.call", "end_call", [[call.id]], {
                activity_name: call.activity.res_name,
            });
            await call.activity.markAsDone();
            call.activity.remove();
            call.activity = null;
        } else {
            data = await this.orm.call("voip.call", "end_call", [[call.id]]);
        }
        this.store.insert(data);
        if (call.timer) {
            clearInterval(call.timer.interval);
            call.timer = null;
        }
    }

    async miss(call) {
        this.store.insert(await this.orm.call("voip.call", "miss_call", [[call.id]]));
        ++this.missedCalls;
    }

    async reject(call) {
        this.store.insert(await this.orm.call("voip.call", "reject_call", [[call.id]]));
    }

    async start(call) {
        this.store.insert(await this.orm.call("voip.call", "start_call", [[call.id]]));
        call.timer = {};
        // Use the time from the client (rather than call.start_date) to avoid
        // clock skew with the server.
        const timerStart = luxon.DateTime.now();
        const computeDuration = () => {
            call.timer.time = Math.floor((luxon.DateTime.now() - timerStart) / 1000);
        };
        computeDuration();
        call.timer.interval = setInterval(computeDuration, 1000);
    }
}

export const callService = {
    dependencies: ["mail.store", "orm"],
    start(env, services) {
        return new CallService(env, services);
    },
};

registry.category("services").add("voip.call", callService);
