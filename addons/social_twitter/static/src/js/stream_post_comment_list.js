import { StreamPostCommentList } from '@social/js/stream_post_comment_list';
import { StreamPostCommentTwitter } from './stream_post_comment';

import { rpc } from "@web/core/network/rpc";

export class StreamPostCommentListTwitter extends StreamPostCommentList {

    toggleUserLikes(comment) {
        rpc(`/social_twitter/${encodeURIComponent(this.originalPost.stream_id.raw_value)}/like_tweet`, {
            tweet_id: comment.id,
            like: !comment.user_likes,
        });
        this._updateLikes(comment);
    }

    get commentComponent() {
        return StreamPostCommentTwitter;
    }

}
