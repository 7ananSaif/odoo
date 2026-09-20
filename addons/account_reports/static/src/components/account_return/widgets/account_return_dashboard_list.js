import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatDate, parseDate } from "@web/core/l10n/dates";
import { Component, useState, onWillStart } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
const { DateTime } = luxon;


export class AccountReturnDashboardList extends Component {
    static template = "account_reports.account_return_dashboard_list";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.accountReturns = useState([]);
        onWillStart(this.fetchNextReturns);
    }

    formatReturn(accountReturn) {
        const deadlineDate = parseDate(accountReturn.date_deadline);
        const now = DateTime.now().startOf('day');
        const daysDiff = deadlineDate.diff(now, 'days').days;

        let deadlineDisplay;
        let deadlineClass = '';

        if (daysDiff < -1) {
            deadlineDisplay = formatDate(deadlineDate);
            deadlineClass = 'text-danger';
        } else if (daysDiff === -1) {
            deadlineDisplay = _t("Yesterday");
            deadlineClass = 'text-danger';
        } else if (daysDiff === 0) {
            deadlineDisplay = _t("Today");
            deadlineClass = 'text-warning';
        } else if (daysDiff === 1) {
            deadlineDisplay = _t("Tomorrow");
            deadlineClass = 'text-warning';
        } else if (daysDiff <= 5) {
            deadlineDisplay = _t("In %s days", Math.round(daysDiff));
            deadlineClass = 'text-warning';
        } else {
            deadlineDisplay = _t("In %s days", Math.round(daysDiff));
        }

        return {
            id: accountReturn.id,
            name: accountReturn.name,
            type_id: accountReturn.type_id,
            matchedReturnsCount: accountReturn.matched_returns_count,
            deadline: formatDate(deadlineDate),
            deadlineDisplay,
            deadlineClass,
        };
    }

    async fetchNextReturns() {
        const returns = await this.orm.call(
            'account.return',
            'get_next_return_for_dashboard',
            [this.props.record.resId], //allow_multiple_by_types
        );

        this.accountReturns = returns.map(this.formatReturn);
    }

    /**
     * Opens the Tax Return view filtered by return type.
     * @param {Object} accountReturn - The account return object.
     */
    async openTaxReturn(accountReturn) {
        const returnTypeId = accountReturn?.type_id || '';
        const [viewId, searchViewId] = await this.orm.call("account.return", "get_kanban_view_and_search_view_id", [[accountReturn.id]]);

        let action;
        if (accountReturn.matchedReturnsCount === 1) {
            action = await this.orm.call("account.return", "action_open_account_return", [[accountReturn.id]]);
        }
        else {
            // Open the filtered Tax Return view
            action = {
                name: _t("Tax Return"),
                type: 'ir.actions.act_window',
                res_model: 'account.return',
                views: [
                    [viewId || false, 'kanban'],
                    [false, 'calendar'],
                ],
                search_view_id: [searchViewId || false],
                context: {
                    'search_default_groupby_deadline': 1,
                    'search_default_todo_returns': 1,
                    // Apply name filter using return type
                    'search_default_type_id': returnTypeId,
                },
                domain: [['return_type_category', '=', 'account_return']],
            };
        }
        this.action.doAction(action);
    }
}


export const accountReturnDashboardList = {
    component: AccountReturnDashboardList,
}

registry.category("view_widgets").add("account_return_dashboard_list", accountReturnDashboardList);
