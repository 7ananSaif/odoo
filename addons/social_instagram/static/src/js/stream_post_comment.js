import { StreamPostComment } from '@social/js/stream_post_comment';
import { StreamPostCommentsReplyInstagram } from './stream_post_comments_reply';

export class StreamPostCommentInstagram extends StreamPostComment {

    //--------
    // Getters
    //--------

    get authorPictureSrc() {
        return `https://graph.facebook.com/v17.0/${encodeURIComponent(this.originalPost.instagram_facebook_author_id.raw_value)}/picture`;
    }

    get link() {
        return `https://www.instagram.com/${encodeURIComponent(this.comment.from.name)}`;
    }

    get authorLink() {
        return this.originalPost.post_link.raw_value;
    }

    get isAuthor() {
        return this.comment.from.id === this.props.mediaSpecificProps.instagramAccountId;
    }

    get commentReplyComponent() {
        return StreamPostCommentsReplyInstagram;
    }

    get deleteCommentEndpoint() {
        return '/social_instagram/delete_comment';
    }

    get likesClass() {
        return 'fa-heart';
    }

    get isLikable() {
        return false;
    }

    get isDeletable() {
        return true;
    }

    get isEditable() {
        return false;
    }

}
