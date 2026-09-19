import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, useEffect } from "@odoo/owl";

import { parseLineId } from "@account_reports/js/util";

import { RelationalModel } from "@web/model/relational_model/relational_model";

import { AccountReturnSelectionBadge } from "../../account_return/widgets/account_return_selection_badge";

export class AccountReportLineName extends Component {
    static template = "account_reports.AccountReportLineName";
    static props = {
        lineIndex: Number,
        line: Object,
    };
    static components = {
        Dropdown,
        DropdownItem,
        AccountReturnSelectionBadge,
    }

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.controller = useState(this.env.controller);

        this.lineNameCell = useRef("lineNameCell");

        this.accountStatus = useState({ record: false });
        useEffect(()=> {
            this.loadAuditStatus();
        }, () => [this.props.line]);
    }

    async loadAuditStatus() {
        if (this.props.line.account_status) {
            if (this.accountStatus.record && this.props.line.account_status.id === this.accountStatus.record.resId)
                return;

            const fields = {
                status: {
                    selection: [
                        ['todo', 'To Review'],
                        ['reviewed', 'Reviewed'],
                        ['supervised', 'Supervised'],
                        ['anomaly', 'Anomaly'],
                    ],
                    required: false,
                }
            }


            const model = new RelationalModel(
                this.env,
                {
                    config: {
                        resModel: 'account.audit.account.status',
                        fields: fields,
                        activeFields: fields,
                        openGroupsByDefault: true,
                        isMonoRecord: true
                    },
                    groupsLimit: Number.MAX_SAFE_INTEGER,
                    limit: 1,
                    countLimit: 1,
                },
                {orm: this.orm}
            );

            this.accountStatus.record = new model.constructor.Record(
                model,
                {
                    context: this.env.controller.context,
                    activeFields: fields,
                    fields: fields,
                    resModel: 'account.audit.account.status',
                    resId: this.props.line.account_status.id,
                    resIds: [this.props.line.account_status.id],
                    isMonoRecord: true,
                    mode: 'readonly',
                },
                this.props.line.account_status,
                { manuallyAdded: !this.props.line.account_status.id }
            )
        }
        else if (this.accountStatus.record) {
            this.accountStatus.record = false
        }
    }

    get accountStatusBadgeOptions() {
        return {
            todo: { decoration: "info" },
            reviewed: { decoration: "success" },
            supervised: { decoration: "success" },
            anomaly: { decoration: "danger" },
        };
    }

    get modelName() {
        return parseLineId(this.props.line.id).at(-1)[1];
    }

    //------------------------------------------------------------------------------------------------------------------
    // Caret options
    //------------------------------------------------------------------------------------------------------------------
    get caretOptions() {
        return this.controller.caretOptions[this.props.line.caret_options];
    }

    get hasCaretOptions() {
        return this.caretOptions?.length > 0;
    }

    async caretAction(caretOption) {
        const res = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.controller.options.report_id,
                this.controller.options,
                caretOption.action,
                {
                    line_id: this.props.line.id,
                    action_param: caretOption.action_param,
                },
            ],
            {
                context: this.controller.context,
            }
        );

        return this.action.doAction(res);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Classes
    // -----------------------------------------------------------------------------------------------------------------
    get lineNameClasses() {
        let classes = "text";

        if (this.props.line.unfoldable)
            classes += " unfoldable";

        if (this.props.line.is_draft)
            classes += " draft";

        if (this.props.line.class)
            classes += ` ${ this.props.line.class }`;

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Action
    // -----------------------------------------------------------------------------------------------------------------
    async triggerAction() {
        const res = await this.orm.call(
            "account.report",
            "execute_action",
            [
                this.controller.options.report_id,
                this.controller.options,
                {
                    id: this.props.line.id,
                    actionId: this.props.line.action_id,
                },
            ],
            {
                context: this.controller.context,
            }
        );

        return this.action.doAction(res);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Load more
    // -----------------------------------------------------------------------------------------------------------------
    async loadMore() {
        const newLines = await this.orm.call(
            "account.report",
            "get_expanded_lines",
            [
                this.controller.options.report_id,
                this.controller.options,
                this.props.line.parent_id,
                this.props.line.groupby,
                this.props.line.expand_function,
                this.props.line.progress,
                this.props.line.offset,
                this.props.line.horizontal_split_side,
            ],
        );

        this.controller.setLineVisibility(newLines)
        if (this.controller.areLinesOrdered()) {
            this.controller.updateLinesOrderIndexes(this.props.lineIndex, newLines, true)
        }
        await this.controller.replaceLineWith(this.props.lineIndex, newLines);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Fold / Unfold
    // -----------------------------------------------------------------------------------------------------------------
    toggleFoldable() {
        if (this.props.line.unfoldable)
            if (this.props.line.unfolded)
                this.controller.foldLine(this.props.lineIndex);
            else
                this.controller.unfoldLine(this.props.lineIndex);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Chatter
    // -----------------------------------------------------------------------------------------------------------------
    get isChatterAnnotated() {
        return this.props.line.visible_annotations;
    }

    get isChatterSelected() {
        return this.controller.chatterState.lineId === this.props.line.id;
    }

    async openChatter() {
        if (!this.props.line.chatter) {
            return;
        }

        this.controller.toggleLineChatter({
            resModel: this.props.line.chatter.model,
            resId: this.props.line.chatter.id,
            line_id: this.props.line.id,
        });
    }
}
