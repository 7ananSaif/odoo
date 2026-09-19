import { user } from "@web/core/user";
import { session } from "@web/session";
import { Pager } from "@web/core/pager/pager";
import { useService, useBus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useModel } from "@web/model/model";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { ControlPanelButtons } from "@mrp_workorder/mrp_display/control_panel";
import { MrpDisplayRecord } from "@mrp_workorder/mrp_display/mrp_display_record";
import { MrpWorkcenterDialog } from "./dialog/mrp_workcenter_dialog";
import { makeActiveField } from "@web/model/relational_model/utils";
import { MrpDisplayEmployeesPanel } from "@mrp_workorder/mrp_display/employees_panel";
import { PinPopup } from "@mrp_workorder/components/pin_popup";
import { useConnectedEmployee } from "@mrp_workorder/mrp_display/hooks/employee_hooks";
import { MrpDisplaySearchBar } from "@mrp_workorder/mrp_display/search_bar";
import { CheckboxItem } from "@web/core/dropdown/checkbox_item";
import { Component, onWillRender, onWillStart, useState, useSubEnv } from "@odoo/owl";
import { MrpEmployeeDialog } from "./dialog/mrp_employee_dialog";

const defaultWorkcenterButtons = [
    { id: 0, display_name: _t("Overview") },
    { id: -1, display_name: _t("My WO") },
];

export class MrpDisplay extends Component {
    static template = "mrp_workorder.MrpDisplay";
    static components = {
        ControlPanelButtons,
        MrpDisplayRecord,
        MrpDisplayEmployeesPanel,
        PinPopup,
        MrpDisplaySearchBar,
        CheckboxItem,
        Pager,
    };
    static props = {
        resModel: String,
        action: { type: Object, optional: true },
        models: { type: Object },
        domain: { type: Array },
        display: { type: Object, optional: true },
        context: { type: Object, optional: true },
        groupBy: { type: Array, element: String },
        orderBy: { type: Array, element: Object },
    };

    setup() {
        this.homeMenu = useService("home_menu");
        this.viewService = useService("view");
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.pwaService = useService("pwa");
        this.overlayService = useService("overlay");
        this.menu = useService("menu");
        this.ui = useService("ui");

        this.adminId = false;
        this.barcodeTargetRecordId = false;
        if (
            this.props.context.active_model === "stock.picking.type" &&
            this.props.context.active_id
        ) {
            this.pickingTypeId = this.props.context.active_id;
        }
        useSubEnv({ localStorageName: `mrp_workorder.db_${session.db}.user_${user.userId}` });

        const localStoredWC = JSON.parse(localStorage.getItem(this.env.localStorageName));
        const firstLoad = !localStoredWC;
        const workcenters = [...defaultWorkcenterButtons, ...(firstLoad ? [] : localStoredWC)];
        const activeWorkcenter = this._loadActiveWorkcenter(this.env.localStorageName, workcenters);

        this.state = useState({
            activeResModel: activeWorkcenter ? "mrp.workorder" : this.props.resModel,
            activeWorkcenter,
            workcenters,
            canLoadSamples: false,
            offset: 0,
            limit: this.props.action?.context?.limit,
            firstLoad: firstLoad,
        });
        this.recordCacheIds = [];

        const params = this._makeModelParams();

        this.model = useState(useModel(RelationalModel, params));
        useSubEnv({
            model: this.model,
            reload: async (record = false) => {
                if (record && !record.dismiss) {
                    while (record && record.resModel !== "mrp.production") {
                        record = record._parentRecord;
                    }
                    await record.load();
                    await record.model.notify();
                    for (let i = 0; i < this.model.root.records.length; i++) {
                        if (this.model.root.records[i].resId == record.resId) {
                            this.model.root.records[i] = record;
                        }
                    }
                } else {
                    await this.model.root.load({
                        offset: this.state.offset,
                        limit: this.state.limit,
                    });
                }
                await this.useEmployee.getConnectedEmployees();
            },
        });
        this.useEmployee = useConnectedEmployee(
            "mrp_display",
            this.props.context,
            this.actionService,
            this.dialogService
        );
        this.barcode = useService("barcode");
        useBus(this.barcode.bus, "barcode_scanned", (event) =>
            this._onBarcodeScanned(event.detail.barcode)
        );
        this.notification = useService("notification");
        this.orm = useService("orm");
        onWillStart(async () => {
            this.groups = {
                byproducts: await user.hasGroup("mrp.group_mrp_byproducts"),
                uom: await user.hasGroup("uom.group_uom"),
                workorders: await user.hasGroup("mrp.group_mrp_routings"),
                timer: await user.hasGroup("mrp_workorder.group_mrp_wo_tablet_timer"),
            };
            this.env.searchModel.workorders = this.groups.workorders;
            this.env.searchModel.setWorkcenterFilter(this.state.workcenters);
            await this.useEmployee.getConnectedEmployees(true);
            // select the workcenter received in the context
            if (this.props.context.workcenter_id) {
                this.state.workcenters = await this.orm.searchRead(
                    "mrp.workcenter",
                    [["id", "=", this.state.activeWorkcenter]],
                    ["display_name"]
                );
            }
            if (
                JSON.parse(localStorage.getItem(this.env.localStorageName)) === null &&
                this.group_mrp_routings
            ) {
                this.toggleWorkcenterDialog(false);
            }
            this.state.canLoadSamples = await this.orm.call("mrp.production", "can_load_samples", [
                [],
            ]);
        });

        onWillRender(() => {
            this.defineRelevantRecords();
        });
    }

    removeRecordIdFromCache(id) {
        this.recordCacheIds.splice(this.recordCacheIds.indexOf(id), 1);
    }

    invalidateRecordIdsCache() {
        if (this.recordCacheIds.length) {
            this.recordCacheIds = [];
        }
    }

    async close() {
        await this.homeMenu.toggle();
    }

    async _onBarcodeScanned(barcode) {
        if (
            barcode.startsWith("OBT") ||
            barcode.startsWith("OCD") ||
            Object.values(this.overlayService.overlays).find(
                (o) => o.component.name === "DialogWrapper"
            )
        ) {
            return;
        }
        const production = this.productions.find((mo) => mo.data.name === barcode);
        if (production) {
            return this._onProductionBarcodeScanned(barcode);
        }
        const workorder = this.relevantRecords.find(
            (wo) => wo.data.barcode === barcode && wo.resModel === "mrp.workorder"
        );
        if (workorder) {
            return this._onWorkorderBarcodeScanned(workorder);
        }
        const employee = await this.orm.call("mrp.workcenter", "get_employee_barcode", [barcode]);
        if (employee) {
            return this.useEmployee.setSessionOwner(employee, undefined);
        }
        return this._onProductBarcodeScanned(barcode);
    }

    _onProductBarcodeScanned(barcode) {
        for (const record of this.relevantRecords) {
            if (this.state.activeResModel === "mrp.workorder") {
                // 1. Check if there is a quality check with this product (WO only)
                for (const check of record.data.check_ids.records) {
                    if (check.data.component_barcode === barcode) {
                        return check.component.onClick();
                    }
                }
            }
            // 2. Check if there is a move with this product (WO/MO)
            for (const move of record.data.move_raw_ids.records) {
                if (move.data.product_barcode === barcode && move.data.manual_consumption) {
                    return move.component.onClick();
                }
            }
            if (this.state.activeResModel === "mrp.workorder") {
                // 3. Check if there is a byproduct move on this WO or on the MO but not any WO with this product
                for (const move of record._parentRecord.data.move_byproduct_ids.records) {
                    if (
                        move.data.product_barcode === barcode &&
                        (move.data.operation_id.id === undefined ||
                            move.data.operation_id.id === record.data.operation_id.id)
                    ) {
                        return move.component.onClick();
                    }
                }
            } else {
                // 4. Check if there is a byproduct move with this product (MO only)
                for (const move of record.data.move_byproduct_ids.records) {
                    if (move.data.product_barcode === barcode) {
                        return move.component.onClick();
                    }
                }
            }
        }
    }

    async _onProductionBarcodeScanned(barcode) {
        const searchItem = Object.values(this.env.searchModel.searchItems).find(
            (i) => i.fieldName === "name"
        );
        const autocompleteValue = {
            label: barcode,
            operator: "=",
            value: barcode,
        };
        this.env.searchModel.addAutoCompletionValues(searchItem.id, autocompleteValue);
    }

    _onWorkorderBarcodeScanned(workorder) {
        return workorder.component.onClickHeader();
    }

    get barcodeTargetRecord() {
        const currentAdminId = this.useEmployee.employees.admin.id;
        if (!currentAdminId) {
            // No current admin, no target record.
            return false;
        }
        if (currentAdminId === this.adminId) {
            // We've already found the target record for the current admin, so we can return it
            return this.barcodeTargetRecordId;
        }
        const firstWorking = this.relevantRecords.find((r) =>
            r.data.employee_ids.records.some((e) => e.resId === currentAdminId)
        );
        this.adminId = currentAdminId;
        this.barcodeTargetRecordId = firstWorking
            ? firstWorking.resId
            : this.relevantRecords[0].resId;
        return this.barcodeTargetRecordId;
    }

    get productions() {
        return this.model.root.records;
    }

    get shouldHideNewWorkcenterButton() {
        return this.props.context.shouldHideNewWorkcenterButton || false;
    }

    get workorders() {
        // Returns all workorders
        return this.model.root.records.flatMap((mo) => mo.data.workorder_ids.records);
    }

    get filteredWorkorders() {
        // Returns all workorders, filtered by the currently selected states
        const activeStates = this.env.searchModel.state.workorderFilters.reduce(
            (acc, f) => (f.isActive ? [...acc, f.name] : acc),
            []
        );
        if (!activeStates.length) {
            return this.workorders;
        }
        return this.workorders.filter((wo) => activeStates.includes(wo.data.state));
    }

    async toggleWorkcenter(workcenters) {
        this.state.firstLoad = false;
        localStorage.setItem(this.env.localStorageName, JSON.stringify(workcenters));
        this.state.workcenters = [...defaultWorkcenterButtons, ...workcenters];
        this.env.searchModel.setWorkcenterFilter(this.state.workcenters);
    }

    getProduction(record) {
        if (record.resModel === "mrp.production") {
            return record;
        }
        return this.model.root.records.find((mo) => mo.resId === record.data.production_id.id);
    }

    /**
     * Defines and returns relevant records (Manufacturing or Work Orders) depending of:
     * - state.activeResModel: Display either `mrp.production` or `mrp.workorder`;
     * - state.activeWorkcenter: Display only selected Workcenter's WO;
     * - adminWorkorderIds: Display only WO assigned to this user.
     * @returns {Object[]}
     */
    defineRelevantRecords() {
        const myWorkordersFilter = (wo) =>
            this.adminWorkorderIds.includes(wo.resId) && wo.data.state !== "cancel";
        const workcenterFilter = (wo) =>
            wo.data.workcenter_id.id === this.state.activeWorkcenter && wo.data.state !== "cancel";
        const showMOs = this.state.activeResModel === "mrp.production";
        const filteredRecords = showMOs
            ? this.productions
            : this.filteredWorkorders.filter(
                  this.state.activeWorkcenter === -1 ? myWorkordersFilter : workcenterFilter
              );

        // Separate filtered records depending if they are already in cache or not.
        const [recordsAlreadyInCache, recordsNotInCache] = [[], []];
        for (const record of filteredRecords) {
            this.recordCacheIds.includes(record.resId)
                ? recordsAlreadyInCache.push(record)
                : recordsNotInCache.push(record);
        }

        // Sort records already in cache by their position in this cache.
        recordsAlreadyInCache.sort((rec1, rec2) => {
            const index1 = this.recordCacheIds.indexOf(rec1.id);
            const index2 = this.recordCacheIds.indexOf(rec2.id);
            return index1 - index2;
        });

        if (recordsNotInCache) {
            if (!showMOs) {
                // Sort Work Orders not in cache by their state.
                const statesComparativeValues = {
                    // Smallest value = first. Biggest value = last.
                    progress: 0,
                    ready: 1,
                    pending: 2,
                    waiting: 3,
                    finished: 4,
                };
                recordsNotInCache.sort((wo1, wo2) => {
                    const v1 = statesComparativeValues[wo1.data.state];
                    const v2 = statesComparativeValues[wo2.data.state];
                    const d1 = wo1.data.date_start;
                    const d2 = wo2.data.date_start;
                    return v1 - v2 || d1 - d2;
                });
            }
            const recordIds = recordsNotInCache.map((r) => r.resId);
            this.recordCacheIds.push(...recordIds);
        }
        this._relevantRecords = [...recordsAlreadyInCache, ...recordsNotInCache];
        return this._relevantRecords;
    }

    get relevantRecords() {
        return this._relevantRecords || [];
    }

    get adminWorkorderIds() {
        const adminId = this.useEmployee.employees.admin.id;
        return !adminId
            ? []
            : this.workorders.reduce(
                  (idList, wo) =>
                      wo.data.employee_assigned_ids.resIds.includes(adminId) ||
                      wo.data.employee_ids.resIds.includes(adminId)
                          ? [...idList, wo.resId]
                          : idList,
                  []
              );
    }

    async selectWorkcenter(workcenterId, showcaseId = false) {
        this.invalidateRecordIdsCache();
        await this.useEmployee.getConnectedEmployees();
        if (showcaseId) {
            this.recordCacheIds.push(showcaseId);
        }
        this.state.activeWorkcenter = Number(workcenterId);
        localStorage.setItem(this.env.localStorageName + `.activeWC`, Number(workcenterId));
        this.state.activeResModel = this.state.activeWorkcenter
            ? "mrp.workorder"
            : "mrp.production";
    }

    toggleWorkcenterDialog(showWarning = true) {
        const params = {
            title: _t("Activate your Work Centers"),
            confirm: this.toggleWorkcenter.bind(this),
            disabled: [],
            active: this.state.workcenters.map((wc) => wc.id),
            radioMode: false,
            showWarning: showWarning,
        };
        this.dialogService.add(MrpWorkcenterDialog, params);
    }

    _makeModelParams() {
        /// Define the structure for related fields
        const { resModel, fields } = this.props.models.find((m) => m.resModel === "mrp.production");
        const activeFields = [];
        for (const fieldName in fields) {
            activeFields[fieldName] = makeActiveField();
        }
        const params = {
            config: { resModel, fields, activeFields },
            limit: this.state.limit,
        };
        const workorderFields = this.props.models.find(
            (m) => m.resModel === "mrp.workorder"
        ).fields;
        params.config.activeFields.workorder_ids.related = {
            fields: workorderFields,
            activeFields: workorderFields,
        };
        const moveFields = this.props.models.find((m) => m.resModel === "stock.move").fields;
        const moveFieldsRelated = {
            fields: moveFields,
            activeFields: moveFields,
        };
        const moveLineFields = this.props.models.find(
            (m) => m.resModel === "stock.move.line"
        ).fields;
        moveFieldsRelated.activeFields.move_line_ids.related = {
            fields: moveLineFields,
            activeFields: moveLineFields,
        };
        params.config.activeFields.move_raw_ids.related = moveFieldsRelated;
        params.config.activeFields.move_byproduct_ids.related = moveFieldsRelated;
        params.config.activeFields.move_finished_ids.related = moveFieldsRelated;
        const checkFields = this.props.models.find((m) => m.resModel === "quality.check").fields;
        params.config.activeFields.check_ids.related = {
            fields: checkFields,
            activeFields: checkFields,
        };
        params.config.activeFields.workorder_ids.related.activeFields.move_raw_ids.related = {
            fields: moveFields,
            activeFields: moveFields,
        };
        params.config.activeFields.workorder_ids.related.activeFields.check_ids.related = {
            fields: checkFields,
            activeFields: checkFields,
        };
        const lotFields = this.props.models.find((m) => m.resModel === "stock.lot").fields;
        params.config.activeFields.lot_producing_ids.related = {
            fields: lotFields,
            activeFields: lotFields,
        };
        params.config.activeFields.lot_producing_ids.onChange = true;
        params.config.activeFields.workorder_ids.related.activeFields.check_ids.related.activeFields.lot_ids.related =
            {
                fields: lotFields,
                activeFields: lotFields,
            };
        params.config.activeFields.check_ids.related.activeFields.production_id.related = {
            fields: fields,
            activeFields: fields,
        };
        return params;
    }

    onClickRefresh() {
        this.invalidateRecordIdsCache();
        this.state.limit = this.props.action?.context?.limit;
        this.env.reload();
    }

    _onPagerChanged({ offset, limit }) {
        this.state.offset = offset;
        this.state.limit = limit;
        this.invalidateRecordIdsCache();
        this.env.reload();
    }

    async loadSamples() {
        this.state.canLoadSamples = "disabled";
        await this.orm.call("mrp.production", "action_load_samples", [[]]);
        this.env.reload();
        this.state.canLoadSamples = false;
    }

    get appName() {
        return encodeURIComponent(this.menu.getCurrentApp().name);
    }

    get displayBackButton() {
        return this.env.config.breadcrumbs.length > 1;
    }

    onClickBack() {
        const crumbs = this.env.config.breadcrumbs;
        crumbs[crumbs.length - 2].onSelected();
    }

    popupAddEmployee() {
        this.dialogService.add(
            MrpEmployeeDialog,
            {
                setConnectedEmployees: this.useEmployee.setConnectedEmployees,
                employees: this.useEmployee.employees,
            },
            { onClose: this.env.reload }
        );
    }

    setMaxLimit() {
        this.state.limit = this.model.root.count;
        this.invalidateRecordIdsCache();
        return this.env.reload();
    }

    /**
     * Resolve the active WC id, giving priority to context, then local storage, finally default or false.
     * If the passed workcenter to activate in context is "Overview" (id:0), also save it to local storage.
     * @returns {Number | false} id of the active Workcenter or false if no workcenters
     */
    _loadActiveWorkcenter(localStorageName, workcenters) {
        if (this.props.context.workcenter_id != null) {
            if (this.props.context.workcenter_id == 0) {
                localStorage.setItem(this.env.localStorageName + `.activeWC`, Number(0));
            }
            return this.props.context.workcenter_id;
        } else if (localStorage.getItem(`${localStorageName}.activeWC`) !== null) {
            return Number(JSON.parse(localStorage.getItem(`${localStorageName}.activeWC`)));
        } else if (workcenters && workcenters.length) {
            return workcenters[0].id; // Defaults to the first WC (often All MO).
        }
        return false;
    }

    demoMORecords = [
        {
            id: 1,
            resModel: "mrp.production",
            data: {
                product_id: { id: 0, display_name: "[FURN_8522] Table Top" },
                product_tracking: "serial",
                product_qty: 4,
                product_uom_id: { id: 1, display_name: "Units" },
                qty_producing: 4,
                state: "progress",
                move_raw_ids: {
                    records: [
                        {
                            resModel: "stock.move",
                            data: {
                                product_id: { id: 0, display_name: "[FURN_7023] Wood Panel" },
                                product_uom_qty: 8,
                                product_uom: { id: 1, display_name: "Units" },
                                move_line_ids: {
                                    records: [],
                                },
                            },
                            _parentRecord: {
                                data: {},
                            },
                        },
                    ],
                },
                move_byproduct_ids: { records: [] },
                workorder_ids: {
                    records: [
                        {
                            resModel: "mrp.workorder",
                            data: {
                                id: 1,
                                name: "Manual Assembly",
                                workcenter_id: { id: 1, display_name: "Assembly 1" },
                                check_ids: {
                                    records: [],
                                },
                                employee_ids: { records: [] },
                            },
                        },
                    ],
                },
                display_name: "WH/MO/00013",
                check_ids: { records: [] },
                employee_ids: { records: [] },
                priority: "1",
            },
            fields: {
                state: {
                    selection: [["progress", "In Progress"]],
                    type: "selection",
                },
                priority: {
                    selection: [
                        ["0", "Normal"],
                        ["1", "Urgent"],
                    ],
                    type: "selection",
                },
            },
        },
        {
            id: 2,
            resModel: "mrp.production",
            data: {
                product_id: { id: 0, display_name: "[D_0045_B] Stool (Dark Blue)" },
                product_tracking: "serial",
                product_qty: 1,
                product_uom_id: { id: 1, display_name: "Units" },
                qty_producing: 1,
                state: "confirmed",
                move_raw_ids: { records: [] },
                move_byproduct_ids: { records: [] },
                workorder_ids: {
                    records: [
                        {
                            resModel: "mrp.workorder",
                            data: {
                                id: 1,
                                name: "Assembly  0/6",
                                workcenter_id: { id: 2, display_name: "Assembly 2" },
                                check_ids: {
                                    records: [],
                                },
                                employee_ids: { records: [] },
                            },
                        },
                    ],
                },
                display_name: "WH/MO/00015",
                check_ids: { records: [] },
                employee_ids: { records: [] },
                priority: false,
            },
            fields: {
                state: {
                    selection: [["confirmed", "Confirmed"]],
                    type: "selection",
                },
                priority: {
                    selection: [
                        ["0", "Normal"],
                        ["1", "Urgent"],
                    ],
                    type: "selection",
                },
            },
        },
    ];
}
