import { formatText } from "@mail/js/emojis_mixin";

import { markup } from "@odoo/owl";

import { htmlReplace } from "@web/core/utils/html";

export const SocialPostFormatterRegex = {
    REGEX_AT: /\B@([\w\dÀ-ÿ-.]+)/g,
    REGEX_HASHTAG: /(^|\s|<br>)#([a-zA-Z\d\-_]+)/g,
    REGEX_URL: /http(s)?:\/\/(www\.)?[a-zA-Z0-9@:%_+~#=?&/\-;!.,()'*$]{3,2000}/g,
};

export const SocialPostFormatterMixinBase = {
    /**
     * Add emojis support
     * Wraps links, #hashtag and @tag around anchors
     * Regex from: https://stackoverflow.com/questions/19484370/how-do-i-automatically-wrap-text-urls-in-anchor-tags
     *
     * @param {string|ReturnType<markup>} value
     * @returns {string|ReturnType<markup>} value
     * @private
     */
    _formatPost(value) {
        // add emojis support and escape HTML
        value = formatText(value);
        // highlight URLs
        value = htmlReplace(value, SocialPostFormatterRegex.REGEX_URL, (url) => {
            /**
             * markup: value is a Markup object (either escaped inside htmlReplace or flagged safe),
             * `url` is directly coming from this value, and the regex doesn't do anything crazy to
             * unescape it.
             */
            url = markup(url);
            return markup`<a href='${url}' class='text-truncate' target='_blank' rel='noreferrer noopener'>${url}</a>`;
        });
        return value;
    },

    _getMediaType() {
        return this.props && this.props.mediaType ||
            this.props.record && this.props.record.data.media_type ||
            this.originalPost && this.originalPost.media_type.raw_value || '';
    }

};

export const SocialPostFormatterMixin = (T) => class extends T {
    _formatPost() {
        return SocialPostFormatterMixinBase._formatPost.call(this, ...arguments);
    }
    _getMediaType() {
        return SocialPostFormatterMixinBase._getMediaType.call(this, ...arguments);
    }
};
