import { AccountBankSelection } from "./mock_server/mock_models/account_bank_selection";
import { AccountOnlineLink } from "./mock_server/mock_models/account_online_link";
import { AccountOnlineAccount } from "./mock_server/mock_models/account_online_account";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";

export const accountOnlineSynchronizationModels = {
    AccountBankSelection,
    AccountOnlineLink,
    AccountOnlineAccount,
};

export function defineAccountOnlineSynchronizationModels() {
    return defineModels({ ...mailModels, ...accountOnlineSynchronizationModels });
}
