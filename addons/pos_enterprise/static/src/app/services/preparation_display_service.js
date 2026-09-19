import { registry } from "@web/core/registry";
import { getOnNotified } from "@point_of_sale/utils";
import { useService } from "@web/core/utils/hooks";
import { redirect } from "@web/core/utils/urls";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { WithLazyGetterTrap } from "@point_of_sale/lazy_getter";
import { useState } from "@odoo/owl";
import { debounce } from "@web/core/utils/timing";

const { DateTime } = luxon;

export class PrepDisplay extends WithLazyGetterTrap {
    static DEPENDENCIES = ["orm", "bus_service", "notification", "pos_data"];

    constructor() {
        super(...arguments);
        this.ready = this.setup(...arguments).then(() => this);
    }
    async setup({ env, deps: { pos_data, bus_service, notification, orm } }) {
        this.id = odoo.preparation_display.id;
        this.env = env;
        this.orm = orm;
        this.data = pos_data;
        this.bus = bus_service;
        this.notification = notification;
        this.sound = this.env.services["mail.sound_effects"];

        this.selectedStageId = this.data.models["pos.prep.stage"].getFirst().id;
        this.selectedCategoryIds = new Set();
        this.selectedProductIds = new Set();
        this.selectedPresetIds = new Set();
        this.selectedTimeIds = new Set();
        this.showCategoryFilter = false;
        this.posHasProducts = await this.loadPosHasProducts();
        this.loadingProducts = false;
        this.ringTheBell = debounce(() => {
            this.sound.play("notification");
        }, 1000);

        this.restoreFilterFromLocalStorage();
        this.getPreparationDisplayOrder(null);

        this.orderCountPresets = {};
        this.orderDays = {};
        this.computeOrderCounts();

        this.onNotified = getOnNotified(this.bus, odoo.preparation_display.access_token);
        this.onNotified("LOAD_ORDERS", async (data) => {
            await this.getPreparationDisplayOrder(data.orderId);

            const orderToDisplay = this.data.models["pos.prep.state"].filter(
                (state) => state.prep_line_id.prep_order_id.pos_order_id.id === data.orderId
            );
            const minDuration = Math.min(...orderToDisplay.map((state) => state.timeToShow));

            if (data.sound) {
                if (minDuration) {
                    setTimeout(() => {
                        this.ringTheBell();
                    }, minDuration);
                } else {
                    this.ringTheBell();
                }
            }
            if (data.notification) {
                this.notification.add(data.notification);
            }
            this.computeOrderCounts();
        });
        this.onNotified("CHANGE_STATE_STAGE", (data) => {
            for (const stage of data["pdis_state_stages"]) {
                const state = this.data.models["pos.prep.state"].get(stage.id);
                if (!state) {
                    continue;
                }
                this.filterHistory(state);
                state.stage_id = this.data.models["pos.prep.stage"].get(stage.stage_id);
                state.todo = true;
                state.write_date = stage.last_stage_change;
            }
            for (const [orderId, completion_time] of Object.entries(
                data["prep_order_completion_time"]
            )) {
                const order = this.data.models["pos.prep.order"].get(orderId);
                if (!order) {
                    continue;
                }
                order.completion_time = completion_time;
            }
            this.computeOrderCounts();
        });
        this.onNotified("CHANGE_STATE_STATUS", (lineStatus) => {
            for (const status of lineStatus) {
                const state = this.data.models["pos.prep.state"].get(status.id);
                if (!state) {
                    continue;
                }
                state.todo = status.todo;
                if (state.stage_id.id === this.lastStage.id && state.todo === false) {
                    this.filterHistory(state);
                }
            }
            this.computeOrderCounts();
        });
        this.onNotified("NOTIFICATION", async (data) => {
            if (data.sound) {
                this.ringTheBell();
            }
            if (data.notification) {
                this.notification.add(data.notification);
            }
            this.computeOrderCounts();
        });
        this.bus.addEventListener("BUS:RECONNECT", () => {
            this.ringTheBell();
            this.getPreparationDisplayOrder(null);
        });
    }
    get lastStage() {
        return this.data.models["pos.prep.stage"].getAll()[
            this.data.models["pos.prep.stage"].getAll().length - 1
        ];
    }
    get categories() {
        return this.data.models["pos.category"].getAll();
    }
    filterHistory(state) {
        const previousStage = this.orderNextStage(state.stage_id.id, -1);
        if (!previousStage) {
            return;
        }
        previousStage.recallHistory = previousStage.recallHistory.map(
            (elem) => (elem = elem.filter((historyState) => historyState.id !== state.id))
        );
    }
    selectStage(stageId) {
        this.selectedStageId = stageId;
        this.computeOrderCounts();
    }
    saveFilterToLocalStorage() {
        const localStorageName = `preparation_display_${this.id}.db_${session.db}.user_${user.userId}`;
        localStorage.setItem(
            localStorageName,
            JSON.stringify({
                products: Array.from(this.selectedProductIds),
                categories: Array.from(this.selectedCategoryIds),
                times: Array.from(this.selectedTimeIds),
                presets: Array.from(this.selectedPresetIds),
            })
        );
    }
    restoreFilterFromLocalStorage() {
        const localStorageName = `preparation_display_${this.id}.db_${session.db}.user_${user.userId}`;
        const localStorageData = JSON.parse(localStorage.getItem(localStorageName));

        if (localStorageData) {
            this.selectedCategoryIds = new Set(localStorageData.categories);
            this.selectedProductIds = new Set(localStorageData.products);
            this.selectedTimeIds = new Set(localStorageData.times);
            this.selectedPresetIds = new Set(localStorageData.presets);
        }
    }
    toggleSelection(id, selectedIdsSet, relatedIds, relatedIdsSet) {
        if (selectedIdsSet.has(id)) {
            selectedIdsSet.delete(id);
        } else {
            selectedIdsSet.add(id);
            relatedIds.forEach((relatedId) => relatedIdsSet.delete(relatedId));
        }

        this.saveFilterToLocalStorage();
    }
    toggleCategory(category) {
        const categoryId = category.id;
        const categoryProductIds = this.data.models["product.product"]
            .filter((p) => p.pos_categ_ids.map((categ) => categ.id).includes(categoryId))
            .map((p) => p.id);

        this.toggleSelection(
            categoryId,
            this.selectedCategoryIds,
            categoryProductIds,
            this.selectedProductIds
        );
    }
    toggleProduct(product) {
        const productId = product.id;
        const categoryIds = product.categoryIds;

        this.toggleSelection(
            productId,
            this.selectedProductIds,
            categoryIds,
            this.selectedCategoryIds
        );
    }
    toggleTime(time) {
        this.selectedTimeIds.has(time)
            ? this.selectedTimeIds.delete(time)
            : this.selectedTimeIds.add(time);
        this.saveFilterToLocalStorage();
    }
    togglePreset(presetId) {
        this.selectedPresetIds.has(presetId)
            ? this.selectedPresetIds.delete(presetId)
            : this.selectedPresetIds.add(presetId);
        this.saveFilterToLocalStorage();
    }
    checkStateVisibility(state) {
        const selectedCategoryIds = this.selectedCategoryIds;
        const selectedProductIds = this.selectedProductIds;
        const selectedPresetIds = this.selectedPresetIds;
        const selectedTimeIds = this.selectedTimeIds;
        const now = DateTime.now().startOf("day");
        const timeMap = {
            today: now,
            tomorrow: now.plus({ days: 1 }),
            nextDays: now.plus({ days: 2 }),
        };
        let timeCheck = true;

        if (selectedTimeIds.size) {
            const orderDate = state.prep_line_id.prep_order_id.pos_order_id.preset_time;
            if (!orderDate) {
                timeCheck = selectedTimeIds.has("today");
            } else {
                timeCheck =
                    (selectedTimeIds.has("today") && orderDate.hasSame(timeMap.today, "day")) ||
                    (selectedTimeIds.has("tomorrow") &&
                        orderDate.hasSame(timeMap.tomorrow, "day")) ||
                    (selectedTimeIds.has("next_days") && orderDate >= timeMap.nextDays);
            }
        }

        const categoryMatch =
            selectedCategoryIds.size === 0 ||
            state.categories.some((category) => selectedCategoryIds.has(category.id));
        const productMatch =
            selectedProductIds.size === 0 || selectedProductIds.has(state.product.id);
        const presetId = state.prep_line_id.prep_order_id.pos_order_id.preset_id;
        const presetMatch =
            selectedPresetIds.size === 0 || Boolean(presetId && selectedPresetIds.has(presetId.id));
        const notDoneOrLastStage = state.todo || state.stage_id.id !== this.lastStage.id;

        return (
            notDoneOrLastStage &&
            categoryMatch &&
            productMatch &&
            presetMatch &&
            (timeCheck || (state.timeToShow === 0 && selectedTimeIds.has("now")))
        );
    }
    orderNextStage(stageId, direction = 1) {
        if (stageId === this.lastStage.id && direction === 1) {
            return this.data.models["pos.prep.stage"].getFirst();
        }

        const stages = this.data.models["pos.prep.stage"].getAll();
        const currentStagesIdx = stages.findIndex((stage) => stage.id === stageId);

        return stages[currentStagesIdx + direction] ?? false;
    }
    computeOrderDays() {
        const orderDays = { now: 0, today: 0, tomorrow: 0, next_days: 0 };
        const now = DateTime.now().startOf("day");
        const tomorrow = now.plus({ days: 1 });
        const nextDays = now.plus({ days: 2 });
        const countedOrders = new Set();

        this.data.models["pos.prep.state"].getAll().forEach((state) => {
            const prepOrder = state.prep_line_id.prep_order_id;
            if (
                (!this.selectedStageId || state.stage_id.id === this.selectedStageId) &&
                !countedOrders.has(prepOrder.id) &&
                !state.isStageDone(this.lastStage.id)
            ) {
                countedOrders.add(prepOrder.id);
                const orderDate = prepOrder.pos_order_id.preset_time;
                if (!orderDate || orderDate.hasSame(now, "day")) {
                    orderDays.today++;
                }
                if (orderDate?.hasSame(tomorrow, "day")) {
                    orderDays.tomorrow++;
                }
                if (orderDate && orderDate >= nextDays) {
                    orderDays.next_days++;
                }
                if (!orderDate || state.timeToShow === 0) {
                    orderDays.now++;
                }
            }
        });
        orderDays[0] = countedOrders.size;
        this.orderDays = orderDays;
    }
    computeOrderCountPresets() {
        const allStates = this.data.models["pos.prep.state"].getAll();
        const orderPresets = {};
        this.data.models["pos.preset"].getAll().forEach((preset) => {
            orderPresets[preset.id] = 0;
        });
        const countedOrders = new Set();
        allStates.forEach((state) => {
            const prepOrder = state.prep_line_id.prep_order_id;
            const presetId = prepOrder.pos_order_id.preset_id;
            if (
                (!this.selectedStageId || state.stage_id.id === this.selectedStageId) &&
                presetId &&
                !countedOrders.has(prepOrder.id) &&
                !state.isStageDone(this.lastStage.id)
            ) {
                countedOrders.add(prepOrder.id);
                orderPresets[presetId.id] += 1;
            }
        });
        orderPresets[0] = countedOrders.size;
        this.orderCountPresets = orderPresets;
    }
    computeOrderCounts() {
        if (this.showCategoryFilter) {
            this.computeOrderDays();
            this.computeOrderCountPresets();
        }
    }
    get filteredOrders() {
        const ordersToDisplay = new Map();
        this.data.models["pos.prep.state"].getAll().forEach((state) => {
            if (
                this.checkStateVisibility(state) &&
                (!this.selectedStageId || state.stage_id.id === this.selectedStageId)
            ) {
                const key = state.prep_line_id.prep_order_id.id + "-" + state.stage_id.id;
                if (!ordersToDisplay.has(key)) {
                    ordersToDisplay.set(key, {
                        prepOrder: state.prep_line_id.prep_order_id,
                        stage: state.stage_id,
                        states: [],
                    });
                }
                ordersToDisplay.get(key).states.push(state);
            }
        });
        return Array.from(ordersToDisplay.values()).sort((a, b) => {
            const stageA = a.stage;
            const stageB = b.stage;
            const stageDiff = stageA.sequence - stageB.sequence || stageA.id - stageB.id; // sort by stage

            if (stageDiff) {
                return stageDiff;
            }
            // within the stage, keep the default order unless the state is done then show most recent first.
            let difference;
            const aWriteDate = Math.max(...a.states.map((sate) => sate.write_date.ts));
            const bWriteDate = Math.max(...b.states.map((sate) => sate.write_date.ts));
            if (stageA.id === this.lastStage.id) {
                difference = bWriteDate - aWriteDate;
            } else {
                difference =
                    (a.prepOrder.pos_order_id.preset_time || aWriteDate) -
                    (b.prepOrder.pos_order_id.preset_time || bWriteDate);
            }

            return difference;
        });
    }
    async syncStateStatus(states) {
        const stateStatus = {};
        const stateIds = [];

        for (const state of states) {
            stateIds.push(state.id);
            stateStatus[state.id] = state.todo;
        }
        await this.orm.call(
            "pos.prep.state",
            "change_state_status",
            [stateIds, stateStatus, this.id],
            {}
        );
    }
    async doneOrders(states) {
        states.forEach((state) => (state.todo = false));
        this.syncStateStatus(states);
    }
    async changeStateStage(states, direction = 1) {
        const currentStage = states[0].stage_id;
        const nextStage = this.orderNextStage(currentStage.id, direction);

        const stateIds = [];
        const statesStages = {};

        states.forEach((sate) => {
            stateIds.push(sate.id);
            statesStages[sate.id] = sate.isCancelled ? this.lastStage.id : nextStage.id;
        });
        await this.orm.call(
            "pos.prep.state",
            "change_state_stage",
            [stateIds, statesStages, this.id],
            {}
        );
        if (direction === 1) {
            currentStage.recallHistory.push(states);
        }
    }
    async resetOrders() {
        this.data.models["pos.prep.state"].deleteMany(this.data.models["pos.prep.state"].getAll());
        const stages = this.data.models["pos.prep.stage"].getAll();
        stages.map((stage) => (stage.recallHistory = []));
        await this.data.callRelated("pos.prep.display", "reset", [[this.id]]);
    }
    async loadPosHasProducts() {
        return await this.orm.call("pos.prep.display", "pos_has_valid_product", [], {});
    }
    async loadScenarioRestaurantData() {
        this.loadingProducts = true;
        try {
            await this.orm.call("pos.config", "load_onboarding_restaurant_scenario");
        } finally {
            window.location.reload();
        }
    }
    async getPreparationDisplayOrder(orderId) {
        const orders = await this.orm.call(
            "pos.prep.display",
            "get_preparation_display_order",
            [this.id, orderId],
            {}
        );
        const missingRecords = await this.data.missingRecursive(orders);
        this.data.models.loadConnectedData(missingRecords);
        this.computeOrderCounts();
    }
    exit() {
        redirect("/odoo/action-pos_enterprise.action_preparation_display");
    }
    get displayPresetsFilter() {
        return this.data.models["pos.config"].some((config) => config.use_presets);
    }
}

export const preparationDisplayService = {
    dependencies: PrepDisplay.DEPENDENCIES,
    async start(env, services) {
        return new PrepDisplay({ traps: {}, env, deps: services }).ready;
    },
};

registry.category("services").add("preparation_display", preparationDisplayService);

/**
 * @returns {PrepDisplay}
 */
export function usePrepDisplay() {
    return useState(useService("preparation_display"));
}
