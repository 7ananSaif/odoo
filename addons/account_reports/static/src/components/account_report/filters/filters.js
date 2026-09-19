import { _t } from "@web/core/l10n/translation";
import { status, Component, useState } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { WarningDialog } from "@web/core/errors/error_dialogs";

import { DateTimeInput } from '@web/core/datetime/datetime_input';
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { formatDate, parseDate } from "@web/core/l10n/dates";
const { DateTime } = luxon;
import { user } from "@web/core/user";

export class AccountReportFilters extends Component {
    static template = "account_reports.AccountReportFilters";
    static props = {};
    static components = {
        DateTimeInput,
        Dropdown,
        DropdownItem,
        MultiRecordSelector,
    };

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.controller = useState(this.env.controller);
        if (this.env.controller.cachedFilterOptions.date) {
            this.dateFilter = useState(this.initDateFilters());
        }
        this.budgetName = useState({
            value: "",
            invalid: false,
        });
        this.timeout = null;
    }

    focusInnerInput(selectedItem) {
        selectedItem.el.querySelector(":scope input")?.focus();
    }

    //------------------------------------------------------------------------------------------------------------------
    // Getters
    //------------------------------------------------------------------------------------------------------------------
    get filterExtraOptionsData() {
        return {
            'all_entries': {
                'name': _t("Draft Entries"),
                'group': 'account_readonly',
                'show': this.controller.filters.show_draft,
            },
            'include_analytic_without_aml': {
                'name': _t("Analytic Simulations"),
                'group': 'account_readonly',
            },
            'hierarchy': {
                'name': _t("Hierarchy and Subtotals"),
                'show': this.controller.cachedFilterOptions.display_hierarchy_filter,
            },
            'unreconciled': {
                'name': _t("Unreconciled Entries"),
                'show': this.controller.filters.show_unreconciled,
            },
            'unfold_all': {
                'name': _t("Unfold All"),
                'show': this.controller.filters.show_all,
            },
            'integer_rounding_enabled': {
                'name': _t("Integer Rounding"),
            },
            'consolidation': {
                'name': _t("Consolidation"),
                'show': this.controller.cachedFilterOptions.show_consolidation,
            },
            'hide_0_lines': {
                'name': _t("Hide lines at 0"),
                'ui_filter': true,
                'onSelect': () => this.toggleHideZeroLines(),
                'show': this.controller.filters.show_hide_0_lines !== "never",
            },
            'horizontal_split': {
                'name': _t("Split Horizontally"),
                'ui_filter': true,
                'onSelect': () => this.toggleHorizontalSplit(),
            },
        }
    }

    get selectedHorizontalGroupName() {
        for (const horizontalGroup of this.controller.cachedFilterOptions.available_horizontal_groups) {
            if (horizontalGroup.id === this.controller.cachedFilterOptions.selected_horizontal_group_id) {
                return horizontalGroup.name;
            }
        }
        return _t("None");
    }

    get isHorizontalGroupSelected() {
        return this.controller.cachedFilterOptions.available_horizontal_groups.some((group) => {
            return group.id === this.controller.cachedFilterOptions.selected_horizontal_group_id;
        });
    }

    get selectedTaxUnitName() {
        for (const taxUnit of this.controller.cachedFilterOptions.available_tax_units) {
            if (taxUnit.id === this.controller.cachedFilterOptions.tax_unit) {
                return taxUnit.name;
            }
        }
        return _t("Company Only");
    }

    get selectedVariantName() {
        for (const variant of this.controller.cachedFilterOptions.available_variants) {
            if (variant.id === this.controller.cachedFilterOptions.selected_variant_id) {
                return variant.name;
            }
        }
        return _t("None");
    }

    get selectedSectionName() {
        for (const section of this.controller.cachedFilterOptions.sections)
            if (section.id === this.controller.cachedFilterOptions.selected_section_id)
                return section.name;
    }

    get selectedAccountType() {
        let selectedAccountType = this.controller.cachedFilterOptions.account_type.filter(
            (accountType) => accountType.selected,
        );
        if (
            !selectedAccountType.length ||
            selectedAccountType.length === this.controller.cachedFilterOptions.account_type.length
        ) {
            return _t("All");
        }

        const accountTypeMappings = [
            { list: ["trade_receivable", "non_trade_receivable"], name: _t("All Receivable") },
            { list: ["trade_payable", "non_trade_payable"], name: _t("All Payable") },
            { list: ["trade_receivable", "trade_payable"], name: _t("Trade Partners") },
            { list: ["non_trade_receivable", "non_trade_payable"], name: _t("Non Trade Partners") },
        ];

        const listToDisplay = [];
        for (const mapping of accountTypeMappings) {
            if (
                mapping.list.every((accountType) =>
                    selectedAccountType.map((accountType) => accountType.id).includes(accountType),
                )
            ) {
                listToDisplay.push(mapping.name);
                // Delete already checked id
                selectedAccountType = selectedAccountType.filter(
                    (accountType) => !mapping.list.includes(accountType.id),
                );
            }
        }

        return listToDisplay
            .concat(selectedAccountType.map((accountType) => accountType.name))
            .join(", ");
    }

    get selectedAmlIrFilters() {
        const selectedFilters = this.controller.cachedFilterOptions.aml_ir_filters.filter(
            (irFilter) => irFilter.selected,
        );

        if (selectedFilters.length === 1) {
            return selectedFilters[0].name;
        } else if (selectedFilters.length > 1) {
            return _t("%s selected", selectedFilters.length);
        } else {
            return _t("None");
        }
    }

    get availablePeriodOrder() {
        return { descending: _t("Descending"), ascending: _t("Ascending") };
    }

    get periodOrder() {
        return this.controller.cachedFilterOptions.comparison.period_order === "descending"
            ? _t("Descending")
            : _t("Ascending");
    }

    get selectedExtraOptions() {
        const selectedExtraOptions = [];

        if (this.controller.cachedUserGroups.account_readonly && this.controller.filters.show_draft) {
            selectedExtraOptions.push(
                this.controller.cachedFilterOptions.all_entries
                    ? _t("With Draft Entries")
                    : _t("Posted Entries"),
            );
        }
        if (this.controller.filters.show_unreconciled && this.controller.cachedFilterOptions.unreconciled) {
            selectedExtraOptions.push(_t("Unreconciled Entries"));
        }
        if (this.controller.cachedFilterOptions.include_analytic_without_aml) {
            selectedExtraOptions.push(_t("Including Analytic Simulations"));
        }
        return selectedExtraOptions.join(", ");
    }

    get dropdownProps() {
        return {
            shouldFocusChildInput: false,
            hotkeys: {
                arrowright: (navigator) => this.focusInnerInput(navigator.activeItem),
            },
        };
    }

    get dateNavigationOptions() {
        /**
         * Returns custom navigation options to fully navigate the date options with your keyboard.
         */
        const findNearestDropdownItem = (navigator) => {
            for (let i = navigator.activeItemIndex; i >= 0; i--) {
                if (navigator.items[i].target.classList.contains("o-dropdown-item")) {
                    return navigator.items[i];
                }
            }
        };

        return {
            hotkeys: {
                arrowleft: (navigator) => {
                    if (!navigator.activeItem) {
                        return;
                    }
                    const periodType = findNearestDropdownItem(navigator)?.target.dataset.periodType;
                    if (Object.prototype.hasOwnProperty.call(this.dateFilter, periodType)) {
                        this.selectPreviousPeriod(periodType);
                    }
                },
                arrowright: (navigator) => {
                    if (!navigator.activeItem) {
                        return;
                    }
                    const periodType = findNearestDropdownItem(navigator)?.target.dataset.periodType;
                    if (Object.prototype.hasOwnProperty.call(this.dateFilter, periodType)) {
                        this.selectNextPeriod(periodType);
                    }
                },
                enter: {
                    callback: (navigator) => {
                        if (!navigator.activeItem) {
                            return;
                        }

                        /**
                         * Workaround for when we're editing a date field, but meanwhile hovering another dropdown item.
                         * In that case, the active item in the navigator is the hovered one (not necessarily the one
                         * we're editing). We check here if the current focused element on the page is an input (the one
                         * we're editing) and in that case find the encompassing dropdown item and select it.
                         */
                        const focusedElement = document.activeElement;
                        if (focusedElement.nodeName === "INPUT") {
                            for (const navigatorItem of navigator.items) {
                                if (navigatorItem.target.contains(focusedElement)) {
                                    navigatorItem.setActive();
                                    break;
                                }
                            }
                        }

                        const dropdownItem = findNearestDropdownItem(navigator);
                        const isSelected = dropdownItem?.target.classList.contains("selected");
                        const periodType = dropdownItem?.target.dataset.periodType;
                        const mode = dropdownItem?.target.dataset.mode;
                        const inputField =
                            navigator.activeItem.target.nodeName === "INPUT"
                                ? navigator.activeItem.target
                                : dropdownItem?.target.querySelector("input.o_input");
                        if (mode === "view" && periodType) {
                            dropdownItem?.setActive();
                            if (!isSelected) {
                                // Select the period type on first enter.
                                this.dateFilter.editing = false;
                                this.filterClicked({
                                    optionKey: "date.filter",
                                    optionValue: periodType,
                                    reload: true,
                                });
                            } else {
                                // Make the input editable on second enter.
                                this.editDateFilter(periodType, inputField);
                            }
                        } else if (mode === "edit" && periodType) {
                            // Save the edited period and return focus to the dropdown item.
                            this.saveDateFilter(periodType, inputField);
                            dropdownItem?.setActive();
                        } else if (periodType) {
                            // Select the period type and potentially blur an input date field to trigger a save.
                            inputField?.blur();
                            this.selectDateFilter(periodType, true);
                            dropdownItem?.setActive();
                        }
                    },
                    bypassEditableProtection: true,
                },
            },
            shouldFocusChildInput: false,
        };
    }

    get periodLabel() {
        return this.controller.cachedFilterOptions.comparison.number_period > 1 ? _t("Periods") : _t("Period");
    }
    //------------------------------------------------------------------------------------------------------------------
    // Helpers
    //------------------------------------------------------------------------------------------------------------------
    get hasAnalyticGroupbyFilter() {
        return Boolean(this.controller.cachedUserGroups.analytic_accounting) && (Boolean(this.controller.filters.show_analytic_groupby) || Boolean(this.controller.filters.show_analytic_plan_groupby));
    }

    get hasCodesFilter() {
        return Boolean(this.controller.cachedFilterOptions.sales_report_taxes?.operation_category?.goods);
    }

    isExtraOptionFilterShown(option) {
        let data = this.filterExtraOptionsData[option];
        return (
            option in this.controller.cachedFilterOptions &&
            option in this.filterExtraOptionsData &&
            data.show !== false &&
            (data.group === undefined || this.controller.cachedUserGroups[data.group])
        );
    }

    get hasExtraOptionsFilter() {
        return Object.keys(this.filterExtraOptionsData)
                     .some(option => this.isExtraOptionFilterShown(option));
    }

    get hasUIFilter() {
        return Object.entries(this.filterExtraOptionsData)
                     .some(([option, data]) => data.ui_filter && this.isExtraOptionFilterShown(option));
    }

    get isBudgetSelected() {
        return this.controller.cachedFilterOptions.budgets?.some((budget) => {
            return budget.selected;
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Dates
    //------------------------------------------------------------------------------------------------------------------
    // Getters
    dateFrom(optionKey) {
        return DateTime.fromISO(this.controller.cachedFilterOptions[optionKey].date_from);
    }

    dateTo(optionKey) {
        return DateTime.fromISO(this.controller.cachedFilterOptions[optionKey].date_to);
    }

    // Setters
    setDate(optionKey, type, date) {
        if (date) {
            this.controller.cachedFilterOptions[optionKey][`date_${type}`] = date;
            this.applyFilters(optionKey);
        }
        else {
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Date cannot be empty"),
            });
        }
    }

    setDateFrom(optionKey, dateFrom) {
        this.setDate(optionKey, 'from', dateFrom);
    }

    setDateTo(optionKey, dateTo) {
        this.setDate(optionKey, 'to', dateTo);
    }

    dateFilters(mode) {
        switch (mode) {
            case "single":
                return [
                    {
                        name: _t("End of Month"),
                        period: "month",
                        mode: this.dateFilter.editing === "month" ? "edit" : "view",
                    },
                    {
                        name: _t("End of Quarter"),
                        period: "quarter",
                        mode: this.dateFilter.editing === "quarter" ? "edit" : "view",
                    },
                    {
                        name: _t("End of Year"),
                        period: "year",
                        mode: this.dateFilter.editing === "year" ? "edit" : "view",
                    },
                ];
            case "range":
                return [
                    {
                        name: _t("Month"),
                        period: "month",
                        mode: this.dateFilter.editing === "month" ? "edit" : "view",
                    },
                    {
                        name: _t("Quarter"),
                        period: "quarter",
                        mode: this.dateFilter.editing === "quarter" ? "edit" : "view",
                    },
                    {
                        name: _t("Year"),
                        period: "year",
                        mode: this.dateFilter.editing === "year" ? "edit" : "view",
                    },
                ];
            default:
                throw new Error(`Invalid mode in dateFilters(): ${mode}`);
        }
    }

    initDateFilters() {
        const filters = {
            month: 0,
            quarter: 0,
            year: 0,
            return_period: 0,
            editing: false,
        };

        const specifier = this.controller.cachedFilterOptions.date.filter.split('_')[0];
        const periodType = this.controller.cachedFilterOptions.date.period_type;
        // In case the period is fiscalyear it will be computed exactly like a year period.
        const period = periodType === "fiscalyear" ? "year" : periodType;
        // Set the filter value based on the specifier.
        if (Object.prototype.hasOwnProperty.call(filters, period)) {
            filters[period] = this.controller.cachedFilterOptions.date.period || (specifier === 'previous' ? -1 : specifier === 'next' ? 1 : 0);
        }

        return filters;
    }

    getDateFilter(periodType) {
        if (this.dateFilter[periodType] > 0) {
            return `next_${periodType}`;
        } else if (this.dateFilter[periodType] === 0) {
            return `this_${periodType}`;
        } else if (this.dateFilter[periodType] < 0) {
            return `previous_${periodType}`;
        } else {
            return periodType;
        }
    }

    selectDateFilter(periodType, reload = false) {
        if (this.isPeriodSelected(periodType)) {
            return;
        }
        this.dateFilter.editing = false;
        const offsetPeriod = Object.prototype.hasOwnProperty.call(this.dateFilter, periodType);
        this.filterClicked({
            optionKey: "date.filter",
            optionValue: this.getDateFilter(periodType),
            reload: !offsetPeriod && reload,
        });
        if (offsetPeriod) {
            this.filterClicked({
                optionKey: "date.period",
                optionValue: this.dateFilter[periodType],
                reload: reload,
            });
        }
    }

    editDateFilter(periodType, inputField) {
        inputField?.select();
        this.dateFilter.editing = periodType;
    }

    saveDateFilter(periodType, inputField) {
        if (!this.dateFilter.editing) {
            return;
        }
        const enteredValue = inputField?.value;
        let dateFilterOffset = false;
        if (periodType === "month") {
            dateFilterOffset = this._parseMonthOffset(enteredValue);
        } else if (periodType === "quarter") {
            dateFilterOffset = this._parseQuarterOffset(enteredValue);
        } else if (periodType === "year") {
            dateFilterOffset = this._parseYearOffset(enteredValue);
        } else if (periodType === "return_period") {
            dateFilterOffset = this._parseReturnPeriodOffset(enteredValue);
        }
        if (dateFilterOffset !== false) {
            dateFilterOffset -= this.dateFilter[periodType];
            this._changePeriod(periodType, dateFilterOffset);
        }
        inputField?.setSelectionRange(enteredValue.length, enteredValue.length);
        this.dateFilter.editing = false;
    }

    _parseMonthOffset(input) {
        try {
            const monthTo = parseDate(input.trim(), { format: "MMMM yyyy" });
            if (!monthTo.isValid) {
                return false;
            }
            const compareDate = DateTime.now().startOf("month");
            return monthTo.startOf("month").diff(compareDate, "months").months;
        } catch {
            return false;
        }
    }

    _parseQuarterOffset(input) {
        try {
            const quarterTo = parseDate(input.split("-").pop().trim(), { format: "MMM yyyy" });
            if (!quarterTo.isValid) {
                return false;
            }
            const compareDate = DateTime.now().startOf("quarter");
            return quarterTo.startOf("quarter").diff(compareDate, "quarters").quarters;
        } catch {
            return false;
        }
    }

    _parseYearOffset(input) {
        try {
            const yearTo = parseDate(input, { format: "yyyy" });
            if (!yearTo.isValid) {
                return false;
            }
            const compareDate = DateTime.now().startOf("year");
            return yearTo.startOf("year").diff(compareDate, "years").years;
        } catch {
            return false;
        }
    }

    _parseReturnPeriodOffset(input) {
        try {
            const dateTo = parseDate(input.split("-").pop().trim());
            if (!dateTo.isValid) {
                return false;
            }
            const periodicitySettings = this.controller.cachedFilterOptions.return_periodicity;
            const [, compareTo] = this._computeReturnPeriodDates(periodicitySettings, DateTime.now());
            const [, taxPeriodTo] = this._computeReturnPeriodDates(periodicitySettings, dateTo);
            return (
                taxPeriodTo.startOf("month").diff(compareTo.startOf("month"), "months").months /
                periodicitySettings.months_per_period
            );
        } catch {
            return false;
        }
    }

    selectPreviousPeriod(periodType) {
        this._changePeriod(periodType, -1);
    }

    selectNextPeriod(periodType) {
        this._changePeriod(periodType, 1);
    }

    _changePeriod(periodType, increment) {
        this.dateFilter[periodType] = this.dateFilter[periodType] + increment;

        this.controller.updateOption("date.filter", this.getDateFilter(periodType));
        this.controller.updateOption("date.period", this.dateFilter[periodType]);

        this.applyFilters("date.period");
    }

    isPeriodSelected(periodType) {
        return this.controller.cachedFilterOptions.date.filter.endsWith(periodType)
    }

    get shouldDisplayReturnPeriod() {
        const periodicitySettings = this.controller.cachedFilterOptions.return_periodicity;
        if (periodicitySettings) {
            return periodicitySettings.start_day !== 1 || periodicitySettings.start_month !== 1 || ![1, 3, 12].includes(periodicitySettings.months_per_period);
        }

        return false;
    }

    displayPeriod(periodType) {
        const dateTo = DateTime.now();

        if (periodType === "return_period" && !this.controller.cachedFilterOptions.return_periodicity)
            periodType = "month";

        switch (periodType) {
            case "month":
                return this._displayMonth(dateTo);
            case "quarter":
                return this._displayQuarter(dateTo);
            case "year":
                return this._displayYear(dateTo);
            case "return_period":
                return this._displayReturnPeriod(dateTo);
            default:
                throw new Error(`Invalid period type in displayPeriod(): ${ periodType }`);
        }
    }

    _displayMonth(dateTo) {
        return dateTo.plus({ months: this.dateFilter.month }).toFormat("MMMM yyyy");
    }

    _displayQuarter(dateTo) {
        const quarterMonths = {
            1: { 'start': 1, 'end': 3 },
            2: { 'start': 4, 'end': 6 },
            3: { 'start': 7, 'end': 9 },
            4: { 'start': 10, 'end': 12 },
        }

        dateTo = dateTo.plus({ months: this.dateFilter.quarter * 3 });

        const quarterDateFrom = DateTime.utc(dateTo.year, quarterMonths[dateTo.quarter]['start'], 1)
        const quarterDateTo = DateTime.utc(dateTo.year, quarterMonths[dateTo.quarter]['end'], 1)

        return `${ formatDate(quarterDateFrom, {format: "MMM"}) } - ${ formatDate(quarterDateTo, {format: "MMM yyyy"}) }`;
    }

    _displayYear(dateTo) {
        return dateTo.plus({ years: this.dateFilter.year }).toFormat("yyyy");
    }

    _displayReturnPeriod(dateTo) {
        const periodicitySettings = this.controller.cachedFilterOptions.return_periodicity;
        const targetDateInPeriod = dateTo.plus({months: periodicitySettings.months_per_period * this.dateFilter['return_period']})
        const [start, end] = this._computeReturnPeriodDates(periodicitySettings, targetDateInPeriod);
        return formatDate(start) + ' - ' + formatDate(end);
    }

    _computeReturnPeriodDates(periodicitySettings, dateInsideTargettesPeriod) {
        /**
         * This function need to stay consitent with the one inside account_return_type from module account_reports.
         * function_name = _get_period_boundaries
         */
        const startMonth = periodicitySettings.start_month;
        const startDay = periodicitySettings.start_day
        const monthsPerPeriod = periodicitySettings.months_per_period;
        const aligned_date = dateInsideTargettesPeriod.minus({days: startDay - 1})
        let year = aligned_date.year;
        const monthOffset = aligned_date.month - startMonth;

        let periodNumber = Math.floor(monthOffset / monthsPerPeriod) + 1;

        if (dateInsideTargettesPeriod < DateTime.now().set({year: year, month: startMonth, day: startDay})) {
            year -= 1;
            periodNumber = Math.floor((12 + monthOffset) / monthsPerPeriod) + 1;
        }

        let deltaMonth = periodNumber * monthsPerPeriod;

        const endDate = DateTime.utc(year, startMonth, 1).plus({ months: deltaMonth, days: startDay-2})
        const startDate = DateTime.utc(year, startMonth, 1).plus({ months: deltaMonth-monthsPerPeriod }).set({ day: startDay})
        return [startDate, endDate];
    }

    //------------------------------------------------------------------------------------------------------------------
    // Number of periods
    //------------------------------------------------------------------------------------------------------------------
    setNumberPeriods(ev) {
        const numberPeriods = ev.target.value;

        if (numberPeriods >= 1)
            this.controller.cachedFilterOptions.comparison.number_period = parseInt(numberPeriods);
        else
            this.dialog.add(WarningDialog, {
                title: _t("Odoo Warning"),
                message: _t("Number of periods cannot be smaller than 1"),
            });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Records
    //------------------------------------------------------------------------------------------------------------------
    getMultiRecordSelectorProps(resModel, optionKey) {
        return {
            resModel,
            resIds: this.controller.cachedFilterOptions[optionKey],
            update: (resIds) => {
                this.filterClicked({ optionKey: optionKey, optionValue: resIds, reload: true});
            },
        };
    }

    //------------------------------------------------------------------------------------------------------------------
    // Rounding unit
    //------------------------------------------------------------------------------------------------------------------
    roundingUnitName(roundingUnit) {
        return _t("In %s", this.controller.cachedFilterOptions["rounding_unit_names"][roundingUnit][0]);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Generic filters
    //------------------------------------------------------------------------------------------------------------------
    async filterClicked({ optionKey, optionValue = undefined, reload = false}) {
        if (optionValue !== undefined) {
            await this.controller.updateOption(optionKey, optionValue);
        } else {
            await this.controller.toggleOption(optionKey);
        }

        if (reload) {
            await this.applyFilters(optionKey);
        }
    }

    async applyFilters(optionKey = null, delay = 500) {
        // We only call the reload after the delay is finished, to avoid doing 5 calls if you want to click on 5 journals
        if (this.timeout) {
            clearTimeout(this.timeout);
        }

        this.controller.incrementCallNumber();

        this.timeout = setTimeout(async () => {
            if (status(this) !== "destroyed")
                await this.controller.reload(optionKey, this.controller.cachedFilterOptions);
        }, delay);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Custom filters
    //------------------------------------------------------------------------------------------------------------------
    selectJournal(journal) {
        if (journal.model === "account.journal.group") {
            const wasSelected = journal.selected;
            this.ToggleSelectedJournal(journal);
            this.controller.cachedFilterOptions.__journal_group_action = {
                action: wasSelected ? "remove" : "add",
                id: parseInt(journal.id),
            };
            // Toggle the selected status after the action is set
            journal.selected = !wasSelected;
        } else {
            journal.selected = !journal.selected;
        }
        this.applyFilters("journals");
    }

    ToggleSelectedJournal(selectedJournal) {
        if (selectedJournal.selected) {
            this.controller.cachedFilterOptions.journals.forEach((journal) => {
                journal.selected = false;
            });
        } else {
            this.controller.cachedFilterOptions.journals.forEach((journal) => {
                journal.selected = selectedJournal.journals.includes(journal.id) && journal.model === "account.journal";
            });
        }
    }

    unfoldCompanyJournals(selectedCompany) {
        let inSelectedCompanySection = false;
        for (const journal of this.controller.cachedFilterOptions.journals) {
            if (journal.id === "divider" && journal.model === "res.company") {
                if (journal.name === selectedCompany.name) {
                    journal.unfolded = !journal.unfolded;
                    inSelectedCompanySection = true;
                } else if (inSelectedCompanySection) {
                    break;  // Reached another company divider, exit the loop
                }
            }
            if (inSelectedCompanySection && journal.model === "account.journal") {
                journal.visible = !journal.visible;
            }
        }
    }

    async filterVariant(reportId) {
        this.controller.saveSessionOptions({
            ...this.controller.cachedFilterOptions,
            selected_variant_id: reportId,
            sections_source_id: reportId,
        });
        const cacheKey = this.controller.getCacheKey(reportId, reportId);
        // if the variant hasn't been loaded yet, set up the call number
        if (!(cacheKey in this.controller.loadingCallNumberByCacheKey)) {
            this.controller.incrementCallNumber(cacheKey);
        }
        await this.controller.displayReport(reportId);
    }

    async filterTaxUnit(taxUnit) {
        await this.filterClicked({ optionKey: "tax_unit", optionValue: taxUnit.id});
        this.controller.saveSessionOptions(this.controller.cachedFilterOptions);

        // force the company to those impacted by the tax units, the reload will be force by this function
        user.activateCompanies(taxUnit.company_ids);
    }

    async toggleHideZeroLines() {
        // Avoid calling the database when this filter is toggled; as the exact same lines would be returned; just reassign visibility.
        await this.controller.toggleOption("hide_0_lines", false);

        this.controller.saveSessionOptions(this.controller.cachedFilterOptions);
        this.controller.setLineVisibility(this.controller.lines);
    }

    async toggleHorizontalSplit() {
        await this.controller.toggleOption("horizontal_split", false);
        this.controller.saveSessionOptions(this.controller.cachedFilterOptions);
    }

    async filterRoundingUnit(rounding) {
        await this.controller.updateOption('rounding_unit', rounding, false);

        this.controller.saveSessionOptions(this.controller.cachedFilterOptions);

        this.controller.lines = await this.controller.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.controller.cachedFilterOptions.report_id,
                this.controller.cachedFilterOptions,
                "format_column_values_from_client",
                this.controller.lines,
            ],
            {
                context: this.controller.context,
            }
        );
    }

    async selectHorizontalGroup(horizontalGroupId) {
        if (horizontalGroupId === this.controller.cachedFilterOptions.selected_horizontal_group_id) {
            return;
        }
        await this.filterClicked({ optionKey: "selected_horizontal_group_id", optionValue: horizontalGroupId, reload: true});
    }

    selectBudget(budget) {
        budget.selected = !budget.selected;
        this.applyFilters( 'budgets')
    }

    async createBudget() {
        const budgetName = this.budgetName.value.trim();
        if (!budgetName.length) {
            this.budgetName.invalid = true;
            this.notification.add(_t("Please enter a valid budget name."), {
                type: "danger",
            });
            return;
        }
        const createdId = await this.orm.call("account.report.budget", "create", [
            { name: budgetName },
        ]);
        this.budgetName.value = "";
        this.budgetName.invalid = false;
        const cachedFilterOptions = this.controller.cachedFilterOptions;
        this.controller.reload("budgets", {
            ...cachedFilterOptions,
            budgets: [
                ...cachedFilterOptions.budgets,
                // Selected by default if we don't have any horizontal group selected
                { id: createdId, selected: !this.isHorizontalGroupSelected },
            ],
        });
    }
}
