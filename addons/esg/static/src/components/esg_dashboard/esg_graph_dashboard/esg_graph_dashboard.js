import { Component, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";
import {
    getBorderWhite,
    getColor,
    getCustomColor,
    lightenColor,
    darkenColor,
} from "@web/core/colors/colors";


const colorScheme = cookie.get("color_scheme");
const GRAPH_LABEL_COLOR = getCustomColor(colorScheme, "#111827", "#E4E4E4");

export class EsgGraphDashboard extends Component {
    static template = "esg.GraphDashboard";
    static props = {
        config: {
            type: Object,
        },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        onWillStart(() => loadJS("/web/static/lib/Chart/Chart.js"));
        onMounted(() => {
            this.renderChart();
        });
        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    get config() {
        const config = { ...this.props.config };
        const data = config.data;
        if (config.type === "pie") {
            const colors = data.labels.map((_, index) =>
                getColor(index, colorScheme, data.labels.length)
            );
            const borderColor = getBorderWhite(colorScheme);
            for (const dataset of data.datasets) {
                dataset.backgroundColor = colors;
                dataset.hoverBackgroundColor = colors;
                dataset.borderColor = borderColor;
            }
        } else {
            for (let index = 0; index < data.datasets.length; index++) {
                const dataset = data.datasets[index];
                const itemColor = getColor(index, colorScheme, data.datasets.length);
                if (config.type === "line") {
                    dataset.backgroundColor = getCustomColor(
                        colorScheme,
                        lightenColor(itemColor, 0.5),
                        darkenColor(itemColor, 0.5)
                    );
                    dataset.cubicInterpolationMode = "monotone";
                    dataset.borderColor = itemColor;
                    dataset.borderWidth = 2;
                    dataset.hoverBackgroundColor = dataset.borderColor;
                    dataset.pointRadius = 3;
                    dataset.pointHoverRadius = 6;
                    dataset.pointBackgroundColor = dataset.borderColor;
                } else {
                    dataset.backgroundColor = itemColor;
                    dataset.borderRadius = 4;
                }
            }
        }
        const options = config.options || {};
        if (config.type !== "pie") {
            const scales = options.scales || {};
            const xAxe = scales.x || {};
            if (!xAxe.ticks) {
                xAxe.ticks = {};
            }
            xAxe.ticks.color = GRAPH_LABEL_COLOR;

            const yAxe = scales.y || {};
            if (!yAxe.ticks) {
                yAxe.ticks = {};
            }
            yAxe.ticks.color = GRAPH_LABEL_COLOR;
            scales.x = xAxe;
            scales.y = yAxe;
            options.scales = scales;
            if (options.plugins?.title) {
                options.plugins.title.color = GRAPH_LABEL_COLOR;
            }
        }
        return {
            ...config,
            options,
        }
    }

    renderChart() {
        this.chart = new Chart(this.canvasRef.el, this.config);
    }
}
