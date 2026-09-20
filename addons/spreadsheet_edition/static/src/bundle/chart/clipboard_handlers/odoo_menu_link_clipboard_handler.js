import { AbstractFigureClipboardHandler, registries } from "@odoo/o-spreadsheet";
const { clipboardHandlersRegistries } = registries;

class OdooLinkClipboardHandler extends AbstractFigureClipboardHandler {
    copy(data) {
        const sheetId = this.getters.getActiveSheetId();
        const figure = this.getters.getFigure(sheetId, data.figureId);
        if (!figure) {
            throw new Error(`No figure for the given id: ${data.figureId}`);
        }

        const copiedOdooMenus = [];
        if (figure.tag === "chart") {
            const chartId = this.getters.getChartIdFromFigureId(data.figureId);
            const odooMenuId = this.getters.getChartOdooMenu(chartId);
            copiedOdooMenus.push(odooMenuId);
        } else if (figure.tag === "carousel") {
            const carousel = this.getters.getCarousel(data.figureId);
            for (const item of carousel.items) {
                if (item.type === "chart") {
                    const odooMenuId = this.getters.getChartOdooMenu(item.chartId);
                    copiedOdooMenus.push(odooMenuId);
                }
            }
        }

        return { copiedOdooMenus };
    }
    paste(target, clippedContent, options) {
        if (!target.figureId || !clippedContent.copiedOdooMenus) {
            return;
        }
        const { figureId } = target;
        const { copiedOdooMenus } = clippedContent;
        const figure = this.getters.getFigure(target.sheetId, figureId);

        const chartIds = [];
        if (figure.tag === "chart") {
            chartIds.push(this.getters.getChartIdFromFigureId(figureId));
        } else if (figure.tag === "carousel") {
            const carousel = this.getters.getCarousel(figureId);
            for (const item of carousel.items) {
                if (item.type === "chart") {
                    chartIds.push(item.chartId);
                }
            }
        }

        for (let i = 0; i < chartIds.length; i++) {
            const chartId = chartIds[i];
            const odooMenuId = copiedOdooMenus[i];
            if (odooMenuId) {
                this.dispatch("LINK_ODOO_MENU_TO_CHART", {
                    chartId,
                    odooMenuId: odooMenuId.xmlid || odooMenuId.id,
                });
            }
        }
    }
}

clipboardHandlersRegistries.figureHandlers.add("odoo_menu_link", OdooLinkClipboardHandler);
