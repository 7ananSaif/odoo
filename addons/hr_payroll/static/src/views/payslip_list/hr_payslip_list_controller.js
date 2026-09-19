import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { _t } from "@web/core/l10n/translation";
import { onWillStart, onWillRender, useState, markup } from "@odoo/owl";
import { PayRunCard } from "../../components/payrun_card/payrun_card";
import { Record } from "@web/model/record";
import { PayslipListRenderer } from "./hr_payslip_list_renderer";
import { parseXML } from "@web/core/utils/xml";
import { useViewCompiler } from "@web/views/view_compiler";
import { PayRunKanbanCompiler } from "../payslip_run_kanban/hr_payslip_run_kanban_compiler";

export class PayslipListController extends ListController {
    static template = "hr_payroll.PayslipListView";
    static components = {
        ...ListController.components,
        PayRunCard,
        Record,
    };

    static KANBAN_CARD_ATTRIBUTE = "card";
    static KANBAN_MENU_ATTRIBUTE = "menu";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.viewService = useService("view");
        this.notificationService = useService("notification");
        this.state = useState({});
        this.revId = 0;
        const viewRegistry = registry.category("views");

        onWillStart(async () => {
            const resModel = "hr.payslip.run";
            const { relatedModels, views } = await this.viewService.loadViews({
                resModel: resModel,
                views: [[false, "kanban"]],
            });
            const { ArchParser } = viewRegistry.get("kanban");
            const xmlDoc = parseXML(views["kanban"].arch);
            const archInfo = new ArchParser().parse(xmlDoc, relatedModels, resModel);
            const { templateDocs: templates } = archInfo;

            this.templates = useViewCompiler(PayRunKanbanCompiler, templates);

            this.payRunArchInfo = archInfo;
            this.props.archInfo.fieldNodes = {
                ...this.props.archInfo.fieldNodes,
                ...archInfo.fieldNodes,
            };
            this.state.payRunInfo = {
                id:
                    this.env.searchModel.domain.find(
                        ([field, operator]) => field === "payslip_run_id" && operator === "="
                    )?.[2] ?? null,
            };
        });

        onWillRender(async () => {
            this.state.payRunInfo.id =
                this.env.searchModel.domain.find(
                    ([field, operator]) => field === "payslip_run_id" && operator === "="
                )?.[2] ?? null;
        });

        this.displayHeaderButtonsTransitions = {
            draft: "action_validate",
            validated: "action_payslip_paid",
            paid: "action_payslip_draft",
        };
    }

    get payrunId() {
        return this.state.payRunInfo.id;
    }

    async onSelectionChanged() {
        await super.onSelectionChanged();
        let selection;
        if ((selection = await this.model.root.getResIds(true))) {
            this.state.selectionStates = await this.orm.read("hr.payslip", selection, ["state"]);
        }
    }

    displayButton(button) {
        if (!Object.values(this.displayHeaderButtonsTransitions).includes(button.clickParams.name)) {
            return true;
        }
        if (
            !this.state.selectionStates
                ?.map((s) => s.state)
                .every((state, i, array) => state === array[0])
        ) {
            return false;
        }
        return (
            button.clickParams.name ===
            this.displayHeaderButtonsTransitions[this.state.selectionStates[0]?.state]
        );
    }

    createNewPayRun() {
        return this.actionService.doAction("hr_payroll.action_hr_payslip_run_create");
    }

    async selectEmployees() {
        const employeeListAction = await this.orm.call(
            "hr.payslip.run",
            "action_payroll_hr_version_list_view_payrun",
            [[this.payrunId]]
        );
        return this.actionService.doAction({
            ...employeeListAction,
            help: markup(employeeListAction.help),
            context: {
                active_id: this.payrunId,
            },
        });
    }

    async onReload() {
        return this.actionService.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }

    async onClose() {
        return this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }

    async addPayslips() {
        const slipIds = await this.model.root.getResIds(true);
        await this.orm.write("hr.payslip", slipIds, {
            payslip_run_id: this.model.config.context.active_id,
        });
        await this.env.model.root.load();
        this.notificationService.add(_t("The payslips(s) are now added to the batch"), {
            type: "success",
        });
        await this.onClose();
        await this.onReload();
    }

    get recordComponentProps() {
        return {
            resModel: "hr.payslip.run",
            resId: this.payrunId,
            fieldNames: Object.values(this.payRunArchInfo.fieldNodes).map((f) => f.name),
            context: this.props.context,
            mode: "readonly",
        };
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name !== "unlink") {
            this.revId++;
        }
        return super.beforeExecuteActionButton(...arguments);
    }

    async afterExecuteActionButton(clickParams) {
        if (clickParams.name === "unlink") {
            const payrun = await this.orm.search("hr.payslip.run", [["id", "=", this.payrunId]]);
            if (!payrun.length) {
                this.env.config.historyBack();
            }
        }
        return super.afterExecuteActionButton(...arguments);
    }

    get actionMenuProps() {
        const res = super.actionMenuProps;
        const oldOnActionExecuted = res.onActionExecuted;
        res.onActionExecuted = () => {
            this.revId++;
            oldOnActionExecuted?.call(res);
        };
        return res;
    }

    onDeleteSelectedRecords() {
        super.onDeleteSelectedRecords();
        this.revId++;
    }
}

export const payslipListView = {
    ...listView,
    Renderer: PayslipListRenderer,
    Controller: PayslipListController,
    buttonTemplate: "hr_payroll.PayslipListView.Buttons",
};

registry.category("views").add("hr_payroll_payslip_list", payslipListView);
