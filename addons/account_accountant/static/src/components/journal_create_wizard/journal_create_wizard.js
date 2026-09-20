import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { user } from "@web/core/user";

class JournalCreateWizardCard extends Component {
    static template = "account.JournalCreateWizardCard";
    static props = ["images", "title", "text"];
}

export class JournalCreateWizard extends Component {
    static template = "account.JournalCreateWizard";
    static props = { ...standardActionServiceProps };
    static components = { JournalCreateWizardCard };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            this.hasGroupAccountUser = await user.hasGroup("account.group_account_user");
        });
    }

    async openAccountWizard(type) {
        const addBankAction = await this.orm.call(
            "res.company",
            `setting_init_${type}_account_action`,
            user.activeCompany.ids
        );
        this.action.doAction(addBankAction);
        this.env.dialogData.close();
    }

    openCreateJournalForm(type) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.journal",
            views: [[false, "form"]],
            target: "current",
            context: { default_type: type },
        });
    }

    cardImages(cardType) {
        const result = cardType === "card" ? ["logo_visa", "logo_mastercard"] : [cardType];
        return result.map((imageName) => `/account_accountant/static/src/img/journal_create_wizard/${imageName}.svg`);
    }

    get cardsData() {
        const data = [
            {
                images: this.cardImages("bank"),
                title: _t("Bank"),
                text: _t("Connect your bank and payment gateways (Paypal, Stripe, ...) or record your transactions manually"),
                onClick: () => this.openAccountWizard("bank"),
            },
            {
                images: this.cardImages("card"),
                title: _t("Card"),
                text: _t("Connect your credit card accounts and manage your payouts"),
                onClick: () => this.openAccountWizard("credit_card"),
            },
            {
                images: this.cardImages("cash"),
                title: _t("Cash"),
                text: _t("Record your cash movements and transfers"),
                onClick: () => this.openCreateJournalForm("cash"),
            },
        ];

        if (this.hasGroupAccountUser) {
            data.push(
                {
                    images: this.cardImages("general"),
                    title: _t("Miscellaneous Journal"),
                    text: _t("Payroll, depreciation, closing entries, deferred revenues, ...etc"),
                    onClick: () => this.openCreateJournalForm("general"),
                },
                {
                    images: this.cardImages("sale"),
                    title: _t("Sales Journal"),
                    text: _t("Create a separate journal for specific sales activities"),
                    onClick: () => this.openCreateJournalForm("sale"),
                },
                {
                    images: this.cardImages("purchase"),
                    title: _t("Purchases Journal"),
                    text: _t("Create a separate journal to organize vendor bills"),
                    onClick: () => this.openCreateJournalForm("purchase"),
                }
            );
        }

        return data;
    }
}

registry.category("actions").add("journal_create_wizard", JournalCreateWizard);
