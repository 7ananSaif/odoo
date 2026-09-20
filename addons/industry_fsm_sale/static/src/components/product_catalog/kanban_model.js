import { rpc } from "@web/core/network/rpc";
import { Record } from "@web/model/relational_model/record";
import { RelationalModel } from "@web/model/relational_model/relational_model";

class ProductCatalogRecord extends Record {
    setup(config, data, options = {}) {
        this.productCatalogData = data.productCatalogData;
        data = { ...data };
        delete data.productCatalogData;
        super.setup(config, data, options);
    }
}

export class FSMProductCatalogKanbanModel extends RelationalModel {
    static Record = ProductCatalogRecord;
    static withCache = false;

    async _loadData(params) {
        const selectedSection = this.env.searchModel.selectedSection;
        if (selectedSection.filtered) {
            params = {
                ...params,
                domain: [
                    ...(params.domain || []),
                    ['is_in_selected_section_of_order', '=', true],
                ],
                context: {
                    ...params.context,
                    section_id: selectedSection.sectionId,
                },
            };
        }
        const result = await super._loadData(params);
        if (!params.isMonoRecord) {
            let records;
            if (params.groupBy?.length) {
                // web_read_group: find all opened records from (sub)group
                records = [];
                const stackGroups = [...result.groups];
                while (stackGroups.length) {
                    const group = stackGroups.pop();
                    if (group.groups?.length) {
                        stackGroups.push(...group.groups);
                    }
                    if (group.records?.length) {
                        records.push(...group.records);
                    }
                }
            } else {
                records = result.records;
            }

            const saleOrderLinesInfo = await rpc("/product/catalog/order_lines_info", {
                order_id: params.context.order_id,
                product_ids: records.map((rec) => rec.id),
                task_id: params.context.fsm_task_id,
                res_model: params.context.product_catalog_order_model,
                child_field: params.context.child_field,
                section_id: this.env.searchModel.selectedSection.sectionId,
            });
            for (const record of records) {
                record.productCatalogData = saleOrderLinesInfo[record.id];
            }
        }
        return result;
    }
}
