import { markup } from "@odoo/owl";

import { SocialPostFormatterMixinBase, SocialPostFormatterRegex } from '@social/js/social_post_formatter_mixin';

import { htmlReplace } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Facebook @tag and #hashtag support.
 * Replace all occurrences of `#hashtag` and of `@tag` by a HTML link to a
 * search of the hashtag/tag on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        const mediaType = this._getMediaType();
        if (['facebook', 'facebook_preview'].includes(mediaType)) {
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
                    return markup`${before}<a href='https://www.facebook.com/hashtag/${hashtag}' target='_blank'>#${hashtag}</a>`;
                }
            );
            const accountId = this.record && this.record.account_id.raw_value ||
                this.originalPost && this.originalPost.account_id.raw_value;
            if (accountId) {
                // Facebook uses a special regex for "@person" support.
                // See social.stream.post#_format_facebook_message for more information.
                const REGEX_AT_FACEBOOK = /\B@\[([0-9]*)\]\s([\w\dÀ-ÿ-]+)/g;
                value = htmlReplace(value, REGEX_AT_FACEBOOK, (_, id, name) => {
                    /**
                     * markup: value is a Markup object (either escaped inside htmlReplace or
                     * flagged safe), `id` and `name` are directly coming from this value, and
                     * the regex doesn't do anything crazy to unescape them.
                     */
                    id = markup(id);
                    name = markup(name);
                    return markup`<a href='/social_facebook/redirect_to_profile/${encodeURIComponent(
                        accountId
                    )}/${id}?name=${name}' target='_blank'>${name}</a>`;
                });
            }
        }
        return value;
    },
});
