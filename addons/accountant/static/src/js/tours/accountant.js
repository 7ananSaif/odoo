/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { accountTourSteps } from "@account/js/tours/account";
import { stepUtils } from "@web_tour/tour_utils";


patch(accountTourSteps, {
    goToAccountMenu(description="Open Accounting Menu") {
        description = _t("Let’s automate your bills, bank transactions and accounting processes.");
        return stepUtils.goToAppSteps('accountant.menu_accounting', description);
    },
});
