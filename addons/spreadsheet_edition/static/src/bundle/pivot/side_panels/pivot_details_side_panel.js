import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { components, stores } from "@odoo/o-spreadsheet";
import { Component, onWillStart, onWillUpdateProps, useRef } from "@odoo/owl";
import { OdooPivotLayoutConfigurator } from "./odoo_pivot_layout_configurator/odoo_pivot_layout_configurator";
import { SidePanelDomain } from "../../components/side_panel_domain/side_panel_domain";
import { RelatedFiltersSection } from "../../global_filters/components/related_filters_section/related_fitlers_section";

const { Checkbox, Section, ValidationMessages, PivotTitleSection, PivotDeferUpdate } = components;
const { useLocalStore, PivotSidePanelStore } = stores;

export class PivotDetailsSidePanel extends Component {
    static template = "spreadsheet_edition.PivotDetailsSidePanel";
    static components = {
        ValidationMessages,
        Checkbox,
        Section,
        OdooPivotLayoutConfigurator,
        PivotDeferUpdate,
        PivotTitleSection,
        RelatedFiltersSection,
        SidePanelDomain,
    };
    static props = {
        onCloseSidePanel: Function,
        pivotId: String,
    };

    setup() {
        this.notification = useService("notification");
        /**@type {PivotSidePanelStore} */
        this.store = useLocalStore(PivotSidePanelStore, this.props.pivotId);
        this.pivotSidePanelRef = useRef("pivotSidePanel");

        const loadData = async () => {
            await this.pivot.load();
            this.modelDisplayName = this.isModelValid && (await this.pivot.getModelLabel());
        };
        onWillStart(loadData);
        onWillUpdateProps(loadData);
    }

    get isModelValid() {
        return this.pivot.isModelValid();
    }

    /** @returns {import("@spreadsheet/pivot/odoo_pivot").default} */
    get pivot() {
        return this.store.pivot;
    }

    getScrollableContainerEl() {
        return this.pivotSidePanelRef.el;
    }

    /**
     * Get the last update date, formatted
     *
     * @returns {string} date formatted
     */
    getLastUpdate() {
        const lastUpdate = this.pivot.lastUpdate;
        if (lastUpdate) {
            return new Date(lastUpdate).toLocaleTimeString();
        }
        return _t("never");
    }

    onDomainUpdate(domain) {
        this.store.update({ domain });
    }

    get unusedPivotWarning() {
        return _t("This pivot is not used");
    }

    get invalidPivotModel() {
        const model = this.env.model.getters.getPivotCoreDefinition(this.props.pivotId).model;
        return _t(
            "The model (%(model)s) of this pivot is not valid (it may have been renamed/deleted). Please re-insert a new pivot.",
            {
                model,
            }
        );
    }

    get deferUpdatesLabel() {
        return _t("Defer updates");
    }

    get deferUpdatesTooltip() {
        return _t(
            "Changing the pivot definition requires to reload the data. It may take some time."
        );
    }

    onDimensionsUpdated(definition) {
        this.store.update(definition);
    }

    flipAxis() {
        const { rows, columns } = this.store.definition;
        this.onDimensionsUpdated({
            rows: columns,
            columns: rows,
        });
    }

    delete() {
        this.env.model.dispatch("REMOVE_PIVOT", { pivotId: this.props.pivotId });
    }
}
