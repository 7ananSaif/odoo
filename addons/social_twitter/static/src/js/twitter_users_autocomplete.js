import { AutoComplete } from "@web/core/autocomplete/autocomplete";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class TwitterUsersAutocompleteField extends CharField {
    static template = "social_twitter.TwitterUsersAutocompleteField";
    static components = {
        ...super.components,
        AutoComplete,
    }

    setup() {
        super.setup();

        this.orm = useService("orm");
        this.value = "";
    }

    async selectTwitterUser(twitterUser) {
        this.value = twitterUser.name;
        const twitterAccountId = await this.orm.call(
            'social.twitter.account',
            'create',
            [{
                name: twitterUser.name,
                twitter_id: twitterUser.id
            }]
        );

        await this.props.record.update({
            twitter_followed_account_id: { id: twitterAccountId, display_name: twitterUser.name },
        });
    }

    get sources() {
        return [{
            optionSlot: "option",
            options: async (request) => {
                if(request.length < 2) {
                    return [];
                }
                const accountId = this.props.record.data.account_id.id;
                const userInfo = await this.orm.call(
                    'social.account',
                    'twitter_get_user_by_username',
                    [[accountId], request]
                );
                const options = [];
                if (userInfo) {
                    options.push({
                        data: userInfo,
                        label: `${userInfo.name} - @${userInfo.username}`,
                        onSelect: () => this.selectTwitterUser(userInfo),
                    });
                }
                return options;
            }
        }];
    }
}

export const twitterUsersAutocompleteField = {
    ...charField,
    component: TwitterUsersAutocompleteField,
};

registry.category("fields").add("twitter_users_autocomplete", twitterUsersAutocompleteField);
