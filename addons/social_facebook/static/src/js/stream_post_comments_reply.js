import { StreamPostCommentsReply } from '@social/js/stream_post_comments_reply';

export class StreamPostCommentsReplyFacebook extends StreamPostCommentsReply {

    get authorPictureSrc() {
        return `https://graph.facebook.com/v17.0/${encodeURIComponent(this.props.mediaSpecificProps.pageFacebookId)}/picture?height=48&width=48`;
    }

    get addCommentEndpoint() {
        return '/social_facebook/comment';
    }

}
