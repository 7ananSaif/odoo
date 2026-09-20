    import { _t } from "@web/core/l10n/translation";
    import { registry } from "@web/core/registry";
    import { patch } from "@web/core/utils/patch";
    import { markup } from "@odoo/owl";
    import { accountTourSteps } from "@account/js/tours/account";

    patch(accountTourSteps, {
        draftBillSelector:
            ":has(.o_radio_input[data-value=in_invoice]:checked):has(.o_arrow_button_current[data-value=draft])",
        newInvoice() {
            return [
                {
                    trigger: "button[name=action_create_new]",
                    content: _t("Now, we'll create your first invoice (accountant)"),
                    run: "click",
                }
            ]
        },
        endSteps() {
            return [
                {
                    trigger: ".dropdown-item[data-menu-xmlid='account.menu_board_journal_1']",
                    content: _t("You can now go back to the dashboard."),
                    tooltipPosition: "bottom",
                    run: "click",
                },
            ];
        },
    });


    registry.category("web_tour.tours").add('account_accountant_tour', {
            url: "/odoo",
            steps: () => [
            ...accountTourSteps.goToAccountMenu().map(step => ({
                ...step,
                // A little hack since the user will come from the account tour which we make sure to make him go to the
                // dashboard in endSteps(), so we want to resume from there.
                isActive: ['auto'].concat(step.isActive || []),
            })),
            // The tour will stop here if there is at least 1 vendor bill in the database.
            // While not ideal, it is ok, since that means the user obviously knows how to create a vendor bill...
            {
                trigger: 'a[name="action_create_vendor_bill"]',
                content: markup(_t('Create your first vendor bill.<br/><br/><i>Tip: If you don’t have one on hand, use our sample bill.</i>')),
                tooltipPosition: 'bottom',
                run: "click",
            }, {
                trigger: `.o_form_view_container${accountTourSteps.draftBillSelector} button.btn-primary[name='action_post']`,
                content: _t('After the data extraction, check and validate the bill. If no vendor has been found, add one before validating.'),
                tooltipPosition: 'bottom',
                run: "click",
            }, {
                trigger: '.dropdown-item[data-menu-xmlid="account.menu_board_journal_1"]',
                content: _t('Let’s go back to the dashboard.'),
                tooltipPosition: 'bottom',
                run: "click",
            }, {
                trigger: 'a[name="open_action"] span:contains(bank)',
                content: _t('Connect your bank and get your latest transactions.'),
                tooltipPosition: 'bottom',
                run: "click",
            }, {
                isActive: ["auto"],
                trigger: ".o_bank_reconciliation_container",
            }, {
                trigger: ".o_bank_rec_widget_kanban_view button.o-kanban-button-new",
                content: _t('Create a new transaction.'),
                tooltipPosition: "bottom",
                run: "click",
            }, {
                trigger: ".o_bank_rec_widget_kanban_view div[name=amount] input",
                content: _t("Set an amount."),
                tooltipPosition: "bottom",
                run: "edit -19250.00",
            }, {
                trigger: ".o_bank_rec_widget_kanban_view div[name=payment_ref] input[id=payment_ref_0]",
                content: _t("Set the payment reference."),
                tooltipPosition: "bottom",
                run: "edit Payment Deco Adict",
            }, {
                trigger: ".o_bank_rec_widget_kanban_view button.o_kanban_edit",
                content: _t("Confirm the transaction."),
                tooltipPosition: "bottom",
                run: "click",
            }, {
                isActive: ["auto"],
                trigger: '.o_kanban_renderer:not(:has(.o_bank_reconciliation_quick_create))',
            }, {
                isActive: ["auto"],
                trigger: ".o_bank_reconciliation_container",
            }, {
                trigger: ".o_bank_rec_widget_kanban_view div[name='bank_statement_line']:first",
                content: _t("Click on the statement to unfold it."),
                tooltipPosition: "bottom",
                run: "click",
            }, {
                isActive: ["auto"],
                trigger: "div.o_button_line",
            }, {
                trigger: '.dropdown-item[data-menu-xmlid="account.menu_board_journal_1"]',
                content: _t('Let’s go back to the dashboard.'),
                run: "click",
            }
        ]
    });
