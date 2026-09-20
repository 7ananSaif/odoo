import { markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Twitter @tag and #hashtag support.
 * Replace all occurrences of `#hashtag` by a HTML link to a search of the hashtag
 * on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (this._getMediaType() === "twitter") {
            value = htmlReplace(
                value,
                SocialPostFormatterRegex.REGEX_HASHTAG,
                (_, before, hashtag) => {
                    // markup: the regex safely captures `before` and `hashtag`
                    before = markup(before);
                    hashtag = markup(hashtag);
                    return markup`${before}<a href='https://twitter.com/hashtag/${encodeURIComponent(
                        hashtag
                    )}?src=hash' target='_blank'>#${hashtag}</a>`;
                }
            );
            value = htmlReplace(value, SocialPostFormatterRegex.REGEX_AT, (_, name) => {
                // markup: the regex safely captures `name`
                name = markup(name);
                return markup`<a href='https://twitter.com/${encodeURIComponent(
                    name
                )}' target='_blank'>@${name}</a>`;
            });
        }
        return value;
    },
});
