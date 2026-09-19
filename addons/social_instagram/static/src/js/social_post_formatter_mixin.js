import { markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Instagram #hashtag and @mention support.
 * Replace all occurrences of `#hashtag` and `@mention` by a HTML link to a
 * search of the hashtag/mention on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (this._getMediaType() === "instagram") {
            value = htmlReplace(
                value,
                SocialPostFormatterRegex.REGEX_HASHTAG,
                (_, before, hashtag) => {
                    /**
                     * markup: value is a Markup object (either escaped inside htmlReplace or
                     * flagged safe), `before` and `hashtag` are directly coming from this value,
                     * and the regex doesn't do anything crazy to unescape them.
                     */
                    before = markup(before);
                    hashtag = markup(hashtag);
                    return markup`${before}<a href='https://www.instagram.com/explore/tags/${hashtag}' target='_blank'>#${hashtag}</a>`;
                }
            );
            value = htmlReplace(value, SocialPostFormatterRegex.REGEX_AT, (_, name) => {
                /**
                 * markup: value is a Markup object (either escaped inside htmlReplace or flagged
                 * safe), `name` is directly coming from this value, and the regex doesn't do
                 * anything crazy to unescape it.
                 */
                name = markup(name);
                return markup`<a href='https://www.instagram.com/${name}' target='_blank'>@${name}</a>`;
            });
        }
        return value;
    },
});
