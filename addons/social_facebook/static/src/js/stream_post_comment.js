import { StreamPostComment } from '@social/js/stream_post_comment';
import { StreamPostCommentsReplyFacebook } from './stream_post_comments_reply';
import { formatFacebookReactions } from './utils';

export class StreamPostCommentFacebook extends StreamPostComment {

    //--------
    // Getters
    //--------

    get authorLink() {
        if (this.comment.from.id) {
            return `/social_facebook/redirect_to_profile/${encodeURIComponent(this.props.mediaSpecificProps.accountId)}/${encodeURIComponent(this.comment.from.id)}?name=${encodeURIComponent(this.comment.from.name)}`;
        } else {
            return "#";
        }
    }

    get authorPictureSrc() {
        if (this.comment.from && this.comment.from.picture) {
            return this.comment.from.picture.data.url;
        } else {
            return '/web/static/img/user_placeholder.jpg';
        }
    }

    get commentReplyComponent() {
        return StreamPostCommentsReplyFacebook;
    }

    get deleteCommentEndpoint() {
        return '/social_facebook/delete_comment';
    }

    get isAuthor() {
        return this.comment.from.id === this.props.mediaSpecificProps.pageFacebookId;
    }

    get link() {
        return `https://www.facebook.com/${encodeURIComponent(this.comment.id)}`;
    }

    /**
     * Return the reactions and the count for each of them.
     */
    get facebookReactions() {
        return formatFacebookReactions(this.comment.reactions);
    }
}
