import { markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Youtube #hashtag support.
 * Replace all occurrences of `#hashtag` by a HTML link to a search of the hashtag
 * on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (["youtube", "youtube_preview"].includes(this._getMediaType())) {
            value = htmlReplace(
                value,
                SocialPostFormatterRegex.REGEX_HASHTAG,
                (_, before, hashtag) => {
                    // markup: the regex safely captures `before` and `hashtag`
                    before = markup(before);
                    hashtag = markup(hashtag);
                    return markup`${before}<a href='https://www.youtube.com/results?search_query=%23${encodeURIComponent(
                        hashtag
                    )}' target='_blank'>#${hashtag}</a>`;
                }
            );
        }
        return value;
    },
});
