import { StreamPostCommentsReply } from '@social/js/stream_post_comments_reply';

export class StreamPostCommentsReplyYoutube extends StreamPostCommentsReply {

    get authorPictureSrc() {
        return `/web/image/social.account/${encodeURIComponent(this.props.mediaSpecificProps.accountId)}/image/48x48`;
    }

    get canAddImage() {
        return false;
    }

    get addCommentEndpoint() {
        return '/social_youtube/comment';
    }

}
