import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { WithSearch } from "@web/search/with_search/with_search";
import { MrpDisplay } from "@mrp_workorder/mrp_display/mrp_display";
import { Component, onWillStart } from "@odoo/owl";
import { MrpDisplaySearchModel } from "@mrp_workorder/mrp_display/search_model";

// from record.js
const defaultActiveField = { attrs: {}, options: {}, domain: "[]", string: "" };

export class MrpDisplayAction extends Component {
    static template = "mrp_workorder.MrpDisplayAction";
    static components = { WithSearch, MrpDisplay };
    static props = {
        "*": true,
    };

    get fieldsStructure() {
        return {
            "mrp.production": [
                "id",
                "display_name",
                "check_ids",
                "company_id",
                "employee_ids",
                "lot_producing_ids",
                "move_byproduct_ids",
                "move_raw_ids",
                "move_finished_ids",
                "name",
                "product_id",
                "product_qty",
                "product_tracking",
                "product_uom_id",
                "qty_producing",
                "state",
                "workorder_ids",
                "date_start",
                "product_description_variants",
                "priority",
                "log_note",
                "picking_type_auto_close",
                "serial_numbers_count",
                "location_src_id",
                "production_location_id",
            ],
            "mrp.workorder": [
                "id",
                "display_name",
                "current_quality_check_id",
                "duration",
                "is_user_working",
                "move_raw_ids",
                "name",
                "operation_id",
                "product_id",
                "production_id",
                "qty_producing",
                "qty_production",
                "state",
                "workcenter_id",
                "working_state",
                "worksheet",
                "check_ids",
                "employee_ids",
                "product_uom_id",
                "is_last_unfinished_wo",
                "barcode",
                "date_start",
                "allowed_employees",
                "all_employees_allowed",
                "qty_remaining",
                "employee_assigned_ids",
                "product_description_variants",
            ],
            "stock.move": [
                "id",
                "operation_id",
                "product_id",
                "product_uom",
                "product_uom_qty",
                "production_id",
                "quantity",
                "picked",
                "raw_material_production_id",
                "should_consume_qty",
                "workorder_id",
                "check_id",
                "product_barcode",
                "has_tracking",
                "move_line_ids",
                "picking_type_prefill_shop_floor_lots",
                "bom_line_id",
                "byproduct_id",
            ],
            "stock.move.line": ["id", "lot_id", "location_id", "quantity", "picked", "product_id"],
            "quality.check": [
                "id",
                "display_name",
                "company_id",
                "component_id",
                "component_tracking",
                "component_uom_id",
                "lot_ids",
                "name",
                "note",
                "picture",
                "product_id",
                "product_tracking",
                "production_id",
                "quality_state",
                "test_type",
                "title",
                "workcenter_id",
                "workorder_id",
                "worksheet_document",
                "write_date",
                "measure",
                "norm_unit",
                "previous_check_id",
                "next_check_id",
                "component_barcode",
            ],
            "stock.lot": [
                "id",
                "name",
                "display_name"
            ],
        };
    }

    setup() {
        this.viewService = useService("view");
        this.fieldService = useService("field");
        this.orm = useService("orm");
        this.resModel = "mrp.production";
        this.models = [];
        const { context } = this.props.action;
        const domain = [
            ["state", "in", ["confirmed", "progress", "to_close"]],
            "|",
            ["bom_id", "=", false],
            ["bom_id.type", "in", ["normal", "phantom"]],
        ];
        if (context.active_model === "stock.picking.type" && context.active_id) {
            domain.push(["picking_type_id", "=", context.active_id]);
        }
        onWillStart(async () => {
            for (const [resModel, fieldNames] of Object.entries(this.fieldsStructure)) {
                const fields = await this.fieldService.loadFields(resModel, { fieldNames });
                for (const [fName, fInfo] of Object.entries(fields)) {
                    fields[fName] = { ...defaultActiveField, ...fInfo };
                    delete fields[fName].context;
                }

                this.models.push({ fields, resModel });
            }
            const searchViews = await this.viewService.loadViews(
                {
                    resModel: this.resModel,
                    context: this.props.action.context,
                    views: [[false, "search"]],
                },
                {
                    load_filters: true,
                    action_id: this.props.action.id,
                }
            );
            context["limit"] = parseInt(
                await this.orm.call("mrp.workorder", "get_shopfloor_limit", [])
            );
            this.withSearchProps = {
                resModel: this.resModel,
                searchViewArch: searchViews.views.search.arch,
                searchViewId: searchViews.views.search.id,
                searchViewFields: searchViews.fields,
                searchMenuTypes: ["filter", "favorite"],
                irFilters: searchViews.views.search.irFilters,
                context,
                domain,
                orderBy: [
                    { name: "priority", asc: false },
                    { name: "state", asc: false },
                    { name: "date_start", asc: true },
                    { name: "id", asc: true },
                    { name: "name", asc: true },
                ],
                SearchModel: MrpDisplaySearchModel,
                searchModelArgs: context,
                loadIrFilters: true,
            };
        });
    }
}

registry.category("actions").add("mrp_display", MrpDisplayAction);
