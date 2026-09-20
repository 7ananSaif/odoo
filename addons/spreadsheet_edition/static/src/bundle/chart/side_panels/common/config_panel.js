import { IrMenuSelector } from "@spreadsheet_edition/bundle/ir_menu_selector/ir_menu_selector";
import { Domain } from "@web/core/domain";
import { DomainSelector } from "@web/core/domain_selector/domain_selector";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { components, constants } from "@odoo/o-spreadsheet";

import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { RelatedFiltersSection } from "../../../global_filters/components/related_filters_section/related_fitlers_section";
const { Section, ValidationMessages } = components;
const { ChartTerms } = constants;

export class CommonOdooChartConfigPanel extends Component {
    static template = "spreadsheet_edition.CommonOdooChartConfigPanel";
    static components = {
        IrMenuSelector,
        DomainSelector,
        RelatedFiltersSection,
        Section,
        ValidationMessages,
    };
    static props = {
        chartId: String,
        definition: Object,
        updateChart: Function,
        canUpdateChart: Function,
    };

    chartTerms = ChartTerms;

    setup() {
        this.dialog = useService("dialog");
        const loadData = async (chartId) => {
            const dataSource = this.env.model.getters.getChartDataSource(chartId);
            await dataSource.load();
            this.isModelValid = dataSource.isModelValid();
            this.isDataLoaded = dataSource.isReady();
            if (this.isModelValid) {
                this.modelDisplayName = await dataSource.getModelLabel();
            }
        };
        onWillStart(() => loadData(this.props.chartId));
        onWillUpdateProps((nextProps) => loadData(nextProps.chartId));
    }

    get invalidChartModel() {
        const model = this.env.model.getters.getChartDefinition(this.props.chartId).metaData
            .resModel;
        return _t(
            "The model (%(model)s) of this chart is not valid (it may have been renamed/deleted). Please re-insert a new chart.",
            {
                model,
            }
        );
    }

    get model() {
        const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
        return definition.metaData.resModel;
    }

    get domain() {
        const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
        return new Domain(definition.searchParams.domain).toString();
    }

    onNameChanged(title) {
        const definition = {
            ...this.env.model.getters.getChartDefinition(this.props.chartId),
            title,
        };
        const figureId = this.env.model.getters.getFigureIdFromChartId(this.props.chartId);
        this.env.model.dispatch("UPDATE_CHART", {
            chartId: this.props.chartId,
            figureId,
            sheetId: this.env.model.getters.getFigureSheetId(figureId),
            definition,
        });
    }

    /**
     * Get the last update date, formatted
     *
     * @returns {string} date formatted
     */
    getLastUpdate() {
        const dataSource = this.env.model.getters.getChartDataSource(this.props.chartId);
        const lastUpdate = dataSource.lastUpdate;
        if (lastUpdate) {
            return new Date(lastUpdate).toLocaleTimeString();
        }
        return _t("never");
    }

    openDomainEdition() {
        this.dialog.add(DomainSelectorDialog, {
            resModel: this.model,
            domain: new Domain(this.domain).toString(),
            isDebugMode: !!this.env.debug,
            onConfirm: (domain) => {
                const definition = this.env.model.getters.getChartDefinition(this.props.chartId);
                const updatedDefinition = {
                    ...definition,
                    searchParams: {
                        ...definition.searchParams,
                        domain: new Domain(domain).toJson(),
                    },
                };
                const figureId = this.env.model.getters.getFigureIdFromChartId(this.props.chartId);
                this.env.model.dispatch("UPDATE_CHART", {
                    chartId: this.props.chartId,
                    figureId,
                    sheetId: this.env.model.getters.getFigureSheetId(figureId),
                    definition: updatedDefinition,
                });
            },
        });
    }

    get odooMenuId() {
        const menu = this.env.model.getters.getChartOdooMenu(this.props.chartId);
        return menu ? menu.id : undefined;
    }
    /**
     * @param {number | undefined} odooMenuId
     */
    updateOdooLink(odooMenuId) {
        if (!odooMenuId) {
            this.env.model.dispatch("LINK_ODOO_MENU_TO_CHART", {
                chartId: this.props.chartId,
                odooMenuId: undefined,
            });
            return;
        }
        const menu = this.env.model.getters.getIrMenu(odooMenuId);
        this.env.model.dispatch("LINK_ODOO_MENU_TO_CHART", {
            chartId: this.props.chartId,
            odooMenuId: menu.xmlid || menu.id,
        });
    }

    delete() {
        this.env.model.dispatch("DELETE_FIGURE", { figureId: this.props.figureId });
    }
}
