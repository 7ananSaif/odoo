import { _t } from "@web/core/l10n/translation";
import { KeepLast, Race } from "@web/core/utils/concurrency";
import { Model } from "@web/model/model";
import { computeReportMeasures, processMeasure } from "@web/views/utils";
import { browser } from "@web/core/browser/browser";

export const MODES = ["retention", "churn"];
export const TIMELINES = ["forward", "backward"];
export const INTERVALS = {
    day: _t("Day"),
    week: _t("Week"),
    month: _t("Month"),
    quarter: _t("Quarter"),
    year: _t("Year"),
};

/**
 * @typedef {import("@web/search/search_model").SearchParams} SearchParams
 */

export class CohortModel extends Model {
    /**
     * @override
     */
    setup(params) {
        // concurrency management
        this.keepLast = new KeepLast();
        this.race = new Race();
        const _load = this._load.bind(this);
        this._load = (...args) => this.race.add(_load(...args));

        this.metaData = params;
        this.data = null;
        this.searchParams = null;
        this.intervals = INTERVALS;

        const activeInterval = browser.localStorage.getItem(this.storageKey) || params.interval;
        if (Object.keys(this.intervals).includes(activeInterval)) {
            this.metaData.interval = activeInterval;
        }
    }

    /**
     * @param {SearchParams} searchParams
     */
    load(searchParams) {
        const { context, domain } = searchParams;
        this.searchParams = { context, domain };
        const { cohort_interval, cohort_measure } = searchParams.context;
        this.metaData.interval = cohort_interval || this.metaData.interval;

        this.metaData.measure = processMeasure(cohort_measure) || this.metaData.measure;
        this.metaData.measures = computeReportMeasures(
            this.metaData.fields,
            this.metaData.fieldAttrs,
            [this.metaData.measure],
            { sumAggregatorOnly: true }
        );
        return this._load(this.metaData);
    }

    get storageKey() {
        return `scaleOf-viewId-${this.env.config.viewId}`;
    }

    /**
     * @override
     */
    hasData() {
        return this.data.rows.length > 0;
    }

    /**
     * @param {Object} params
     */
    async updateMetaData(params) {
        Object.assign(this.metaData, params);
        browser.localStorage.setItem(this.storageKey, this.metaData.interval);
        await this._load(this.metaData);
        this.notify();
    }

    //--------------------------------------------------------------------------
    // Protected
    //--------------------------------------------------------------------------

    /**
     * @protected
     * @param {Object} metaData
     */
    async _load(metaData) {
        this.data = await this.keepLast.add(this._fetchData(metaData));
        this.data.rows.forEach((row) => {
            row.columns = row.columns.filter((col) => col.percentage !== "");
        });
    }

    /**
     * @protected
     * @param {Object} metaData
     */
    async _fetchData(metaData) {
        const { context, domain } = this.searchParams;
        return this.orm.call(metaData.resModel, "get_cohort_data", [], {
            date_start: metaData.dateStart,
            date_stop: metaData.dateStop,
            measure: metaData.measure,
            interval: metaData.interval,
            domain,
            mode: metaData.mode,
            timeline: metaData.timeline,
            context,
        });
    }
}
