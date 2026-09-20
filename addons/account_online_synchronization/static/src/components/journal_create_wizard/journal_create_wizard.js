import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { JournalCreateWizard } from "@account_accountant/components/journal_create_wizard/journal_create_wizard";
import { useBankInstitutions } from "@account_online_synchronization/hooks/bank_institutions_hook";

patch(JournalCreateWizard.prototype, {
    setup() {
        super.setup();
        this.bankInstitutions = useBankInstitutions();
        onWillStart(async () => {
            this.institutionsPictures = (await this.bankInstitutions.fetch())
                .slice(0, 2)
                .map((institution) => institution.picture);
        });
    },
    cardImages(cardType) {
        return cardType !== "bank" || this.institutionsPictures.length !== 2
            ? super.cardImages(cardType)
            : this.institutionsPictures;
    },
});
