import {
    AccountReturnCheckKanbanRecord
} from "@account_reports/components/account_return/views/account_return_check_kanban_record";
import {KanbanRenderer} from "@web/views/kanban/kanban_renderer";
import {onWillStart, onWillDestroy} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {parseXML} from "@web/core/utils/xml";
import {extractFieldsFromArchInfo, getFieldsSpec} from "@web/model/relational_model/utils";
import {RelationalModel} from "@web/model/relational_model/relational_model";
import {isNull} from "@web/views/utils";
import {AccountReturnKanbanRecord} from "./account_return_kanban_record";
import {Chatter} from "@mail/chatter/web_portal/chatter";


const viewRegistry = registry.category("views");


export class AccountReturnCheckKanbanRenderer extends KanbanRenderer {
    static template = "account_reports.account_return_check_kanban_renderer";

    static components = {
        ...KanbanRenderer.components,
        AccountReturnCheckKanbanRecord,
        AccountReturnKanbanRecord,
        Chatter,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.viewService = useService("view");
        const context = this.props.list.context;
        this.destroyed = false
        this.originalListLoad = this.props.list.model.load.bind(this.props.list.model);

        onWillDestroy(async () => {
            this.destroyed = true;
        });

        if (context.active_model === "account.return") {
            this.currentReturnId = context.active_id

            onWillStart(async () => {
                const { fields, relatedModels, views } = await this.viewService.loadViews({
                    resModel: "account.return",
                    context: context,
                    views: [[context.account_return_view_id, "kanban"]],
                });
                const { ArchParser } = viewRegistry.get("kanban");
                const xmlDoc = parseXML(views["kanban"].arch);
                this.returnArchInfo = new ArchParser().parse(xmlDoc, relatedModels, 'account.return');

                const extractedFields = extractFieldsFromArchInfo(this.returnArchInfo, fields);

                const accountReturnId = this.currentReturnId;
                if (!accountReturnId) return;
                this.specification = getFieldsSpec(extractedFields.activeFields, extractedFields.fields, context)

                const returnData = await this.orm.webRead(
                    'account.return',
                    [accountReturnId],
                    { specification: this.specification }
                );

                const modelParams = this.getModelParams(extractedFields.activeFields, extractedFields.fields);
                const model = new RelationalModel(this.env, modelParams, {orm: this.orm});

                this.returnRecord = new model.constructor.Record(
                    model,
                    {
                        context: { ...context, in_checks_view: true },
                        activeFields: extractedFields.activeFields,
                        resModel: 'account.return',
                        fields: extractedFields.fields,
                        resId: accountReturnId,
                        resIds: [accountReturnId],
                        isMonoRecord: true,
                        mode: 'readonly',
                    },
                    returnData[0],
                    { manuallyAdded: !returnData.id }
                )

                this.props.list.model.load = async (params) => {
                    // Reload return card
                    const result = await this.originalListLoad(params);
                    if (this.destroyed) return result;
                    const returnData = await this.orm.webRead(
                        'account.return',
                        [accountReturnId],
                        { specification: this.specification }
                    );
                    if (this.destroyed) return result;
                    this.returnRecord._setData(returnData[0]);

                    // Reload chatter messages
                    this.env.bus.trigger("MAIL:RELOAD-THREAD", {
                        model: "account.return",
                        id: accountReturnId,
                    });

                    return result;
                };

                // Update records checks
                const records = this.props.list.records;
                if (records.length > 0) {
                    const checkResults = this.orm.call("account.return", "refresh_checks", [this.currentReturnId])
                    checkResults.then(async () => {
                        if (!this.destroyed) {
                            await this.props.list.model.load();
                        }
                    });
                }
            });
        }
    }

    getModelParams(activeFields, fields) {
        const modelConfig = {
            resModel: 'account.return',
            fields,
            activeFields,
            openGroupsByDefault: true,
        };

        return {
            config: modelConfig,
            groupsLimit: Number.MAX_SAFE_INTEGER,
            limit: 1,
            countLimit: 1,
        };
    }

    get groups() {
        const { list } = this.props;
        if (!list.isGrouped) {
            return false;
        }
        return list.groups.map((group, index) => ({
            ...group,
            key: isNull(group.value) ? `group_key_${index}` : String(group.value),
        }));
    }

    async openRecord(record, params) {
        const recordId = record.resId;
        if (record.resModel === "account.return.check") {
            const result = await this.orm.call(
                record.resModel,
                "action_review",
                [recordId]
            );

            if (result) {
                this.action.doAction(result);
            }
        }
    }
}
