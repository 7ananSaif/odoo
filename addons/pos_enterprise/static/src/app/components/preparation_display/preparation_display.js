import { Category } from "@pos_enterprise/app/components/category/category";
import { Stages } from "@pos_enterprise/app/components/stages/stages";
import { Order } from "@pos_enterprise/app/components/order/order";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { usePrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import { Component, onMounted, onPatched, useState } from "@odoo/owl";

export class PrepDisplay extends Component {
    static components = { Category, Stages, Order, MainComponentsContainer };
    static template = `pos_enterprise.PrepDisplay`;
    static props = {};

    setup() {
        this.prepDisplay = usePrepDisplay();
        this.displayName = odoo.preparation_display.name;
        this.showSidebar = true;
        this.onNextPatch = new Set();
        this.state = useState({
            isMenuOpened: false,
            zoom: 1,
        });
        onPatched(() => {
            for (const cb of this.onNextPatch) {
                cb();
            }
            localStorage.setItem("pdis-zoom", this.state.zoom);
        });

        onMounted(() => {
            this.state.zoom = parseFloat(localStorage.getItem("pdis-zoom")) || 1;
        });
    }
    get filterSelected() {
        return (
            this.prepDisplay.selectedCategoryIds.size +
            this.prepDisplay.selectedProductIds.size +
            this.prepDisplay.selectedTimeIds.size +
            this.prepDisplay.selectedPresetIds.size
        );
    }
    get selectedStage() {
        return this.prepDisplay.data.models["pos.prep.stage"].get(this.prepDisplay.selectedStageId);
    }
    changeZoom(value) {
        const currentZoom = parseFloat(this.state.zoom);
        let val = currentZoom + parseFloat(value);
        val = val > 2 ? 2 : val;
        val = val < 0.5 ? 0.5 : val;
        this.state.zoom = val;
    }
    archiveAllVisibleOrders() {
        const lastStageVisibleOrderLines = this.prepDisplay.data.models["pos.prep.state"]
            .getAll()
            .filter((pdisLine) => pdisLine.stage_id === this.prepDisplay.lastStage);

        this.prepDisplay.doneOrders(lastStageVisibleOrderLines);
    }
    resetFilter() {
        this.prepDisplay.selectedCategoryIds = new Set();
        this.prepDisplay.selectedProductIds = new Set();
        this.prepDisplay.selectedTimeIds = new Set();
        this.prepDisplay.selectedPresetIds = new Set();
        this.prepDisplay.saveFilterToLocalStorage();
    }
    toggleCategoryFilter() {
        this.prepDisplay.showCategoryFilter = !this.prepDisplay.showCategoryFilter;
        this.prepDisplay.computeOrderCounts();
    }
    recallLastChange() {
        if (!this.isHistoryEmpty()) {
            this.prepDisplay.changeStateStage(this.selectedStage.recallHistory.pop(), -1, 0);
        } else {
            this.selectedStage.recallHistory.length = 0;
        }
    }
    isHistoryEmpty() {
        const lastElement =
            this.selectedStage.recallHistory[this.selectedStage.recallHistory.length - 1];

        if (lastElement?.some((state) => state?.computeDuration() < 10)) {
            return false;
        }
        return true;
    }
    isBurgerMenuClosed() {
        return !this.state.isMenuOpened;
    }
    closeMenu() {
        this.state.isMenuOpened = false;
    }
    openMenu() {
        this.state.isMenuOpened = true;
    }
    get presets() {
        return this.prepDisplay.data.models["pos.preset"].getAll();
    }
}
