import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { StreamPostCommentsReply } from "@social/js/stream_post_comments_reply";
import {
    contains,
    defineModels,
    models,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

class SocialMedia extends models.ServerModel {
    _name = "social.media";
    _records = [
        {
            id: 1,
            name: "Facebook",
            has_streams: true,
            media_type: "facebook",
        },
    ];
}

class SocialAccount extends models.ServerModel {
    _name = "social.account";
    _records = [
        {
            id: 1,
            name: "Jack's Page",
            is_media_disconnected: false,
            has_account_stats: true,
            has_trends: true,
            audience: 519,
            audience_trend: 50,
            engagement: 6000,
            engagement_trend: 60,
            stories: 70000,
            stories_trend: -20,
            stats_link: "facebook.com/jack",
            media_id: 1,
        },
        {
            id: 2,
            name: "Jhon's Page",
            has_account_stats: true,
            has_trends: false,
            audience: 400,
            audience_trend: 0,
            engagement: 400,
            engagement_trend: 0,
            stories: 4000,
            stories_trend: 0,
            stats_link: "facebook.com/jhon",
            media_id: 1,
        },
    ];
}

class SocialStream extends models.ServerModel {
    _name = "social.stream";
    _records = [
        {
            id: 1,
            name: "Stream 1",
            media_id: 1,
            account_id: 1,
        },
        {
            id: 2,
            name: "Stream 2",
            media_id: 1,
            account_id: 1,
        },
    ];
}

class SocialStreamPostImage extends models.ServerModel {
    _name = "social.stream.post.image";
}

class SocialStreamPost extends models.ServerModel {
    _name = "social.stream.post";
    _records = [
        {
            id: 1,
            author_name: "Jhon",
            post_link: "www.odoosocial.com/link1",
            author_link: "www.odoosocial.com/author1",
            published_date: "2019-08-20 14:16:00",
            formatted_published_date: "2019-08-20 14:16:00",
            message: "Message 1 Youtube",
            link_url: "blog.com/odoosocial",
            link_title: "Odoo Social",
            link_description: "Odoo Social Description",
            facebook_author_id: "1",
            facebook_likes_count: 5,
            facebook_user_likes: true,
            facebook_reactions_count: '{"LIKE": 5}',
            facebook_comments_count: 15,
            facebook_shares_count: 3,
            facebook_reach: 18,
            stream_id: 1,
        },
        {
            id: 2,
            author_name: "Jack",
            post_link: "www.odoosocial.com/link2",
            author_link: "www.odoosocial.com/author2",
            published_date: "2019-08-20 14:17:00",
            formatted_published_date: "2019-08-20 14:17:00",
            message: "Message 2 Images",
            facebook_author_id: "2",
            facebook_likes_count: 10,
            facebook_user_likes: false,
            facebook_reactions_count: '{"LIKE": 10}',
            facebook_comments_count: 25,
            facebook_shares_count: 4,
            facebook_reach: 33,
            stream_id: 2,
        },
        {
            id: 3,
            author_name: "Michel",
            post_link: "www.odoosocial.com/link3",
            author_link: "www.odoosocial.com/author3",
            published_date: "2019-08-20 14:18:00",
            formatted_published_date: "2019-08-20 14:18:00",
            message: "Message 3",
            media_type: "facebook",
            facebook_author_id: "3",
            facebook_likes_count: 0,
            facebook_user_likes: false,
            facebook_reactions_count: "{}",
            facebook_comments_count: 0,
            facebook_shares_count: 0,
            facebook_reach: 42,
            stream_id: 2,
        },
    ];
    _views = {
        kanban: /*xml*/ `
            <kanban class="o_social_stream_post_kanban"
                create="0"
                edit="0"
                records_draggable="false"
                group_create="false"
                js_class="social_stream_post_kanban_view">
                <field name="author_name"/>
                <field name="author_link"/>
                <field name="post_link"/>
                <field name="published_date"/>
                <field name="media_type"/>
                <field name="account_id"/>
                <field name="link_url"/>
                <field name="link_image_url"/>
                <field name="link_title"/>
                <field name="link_description"/>
                <field name="stream_post_image_ids"/>
                <field name="facebook_author_id"/>
                <field name="facebook_user_likes"/>
                <field name="facebook_reactions_count"/>
                <field name="linkedin_author_image_url"/>
                <field name="instagram_facebook_author_id"/>
                <field name="twitter_profile_image_url"/>
                <templates>
                    <t t-name="card" class="o_social_stream_post_kanban_global p-0 mb-3">
                        <div class="o_social_stream_post_message py-2">
                            <div class="d-flex justify-content-between mb-2 px-2">
                                <t t-set="author_info">
                                    <span class="o_social_stream_post_author_image o_social_author_image o_avatar position-relative rounded overflow-hidden"/>
                                    <span class="o_social_stream_post_author_name text-truncate ms-2" t-esc="record.author_name.value or 'Unknown'" t-att-title="record.author_name.value or 'Unknown'"/>
                                </t>

                                <div class="o_social_author_information d-flex align-items-center">
                                    <a t-if="record.author_link.value"
                                        class="d-flex align-items-center"
                                        t-att-href="record.author_link.value"
                                        t-att-title="record.author_name.value or 'Unknown'"
                                        t-out="author_info"
                                        target="_blank"/>

                                    <div t-else=""
                                        class="d-flex align-items-center"
                                        t-out="author_info"/>
                                </div>

                                <a t-att-href="record.post_link.value" target="_blank" class="o_social_stream_post_published_date small" t-att-title="record.published_date.value">
                                    <field name="formatted_published_date"/>
                                </a>
                            </div>
                            <div name="o_social_stream_post_message_body"
                                class="o_social_stream_post_message_body px-2 pb-2 mb-2 border-bottom}">
                                <field name="message" widget="social_post_formatter" class="o_social_stream_post_message_text overflow-hidden mb-2"/>
                            </div>
                            <div class="o_social_stream_post_facebook_stats px-2 d-flex justify-content-around"
                                t-if="record.media_type.raw_value === 'facebook'">
                                <div t-if="record.facebook_likes_count.raw_value !== 0" t-attf-class="o_social_facebook_likes o_social_subtle_btn ps-2 pe-3 #{record.facebook_user_likes.raw_value ? 'o_social_facebook_user_likes' : ''}">
                                    <i class="fa fa-thumbs-up me-1" title="Likes"/>
                                    <field name="facebook_likes_count" class="fw-bold"/>
                                </div>
                                <div class="o_social_facebook_comments o_social_comments o_social_subtle_btn px-3">
                                    <i class="fa fa-comments me-1" title="Comments"/>
                                    <field t-if="record.facebook_comments_count.value !== '0'" name="facebook_comments_count" class="fw-bold"/>
                                </div>
                                <div class="flex-grow-1 d-flex text-muted justify-content-end">
                                    <field name="facebook_shares_count" class="me-1"/>
                                    Shares
                                    <div class="ms-3">
                                        <field name="facebook_reach"/>
                                        Views
                                    </div>
                                </div>
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        `,
    };
}

class SocialLivePost extends models.ServerModel {
    _name = "social.live.post";
}

defineMailModels();
defineModels([
    SocialMedia,
    SocialAccount,
    SocialStream,
    SocialStreamPostImage,
    SocialStreamPost,
    SocialLivePost,
]);

function mockStatsRpc({ checkSteps } = {}) {
    onRpc(["refresh_all", "refresh_statistics"], ({ model, method }) => {
        if (checkSteps) {
            expect.step(`[${model}] ${method}`);
        }
        return {};
    });
}

onRpc("https://graph.facebook.com/", () => "");

test("Check accounts statistics", async () => {
    mockStatsRpc({ checkSteps: true });
    await mountView({
        type: "kanban",
        resModel: "social.stream.post",
    });
    expect.verifySteps([
        "[social.stream] refresh_all",
        "[social.live.post] refresh_statistics",
        "[social.account] refresh_statistics",
    ]);
    expect(".o_social_stream_stat_box").toHaveCount(2, {
        message: "Kanban View should contain exactly 2 lines of account statistics.",
    });
    // 2 because '50%' and `60%` counts as a match
    // so if we want to check that there are no actual 0%, it means we want only 2 times "contains 0%"
    expect(".o_social_stream_stat_box small:contains('0%')").toHaveCount(2, {
        message: "Accounts with has_trends = false should not display trends.",
    });
    expect(".o_social_stream_stat_box b:contains('519')").toHaveCount(1, {
        message: "Audience is correctly displayed.",
    });
    expect(".o_social_stream_stat_box small:contains('50%')").toHaveCount(1, {
        message: "Audience trend is correctly displayed.",
    });
    expect(".o_social_stream_stat_box small:contains('60%')").toHaveCount(1, {
        message: "Engagement trend is correctly displayed.",
    });
});

test("Check messages display", async () => {
    mockStatsRpc();
    await mountView({
        type: "kanban",
        resModel: "social.stream.post",
    });
    expect(".o_social_stream_post_kanban_global").toHaveCount(3, {
        message: "There should be 3 posts displayed on kanban view.",
    });
    expect(
        ".o_social_stream_post_kanban_global:first-child .o_social_stream_post_facebook_stats .o_social_facebook_likes"
    ).toHaveText("5", { message: "The first post should have 5 likes" });
    expect(
        ".o_social_stream_post_kanban_global:first-child .o_social_stream_post_facebook_stats .o_social_facebook_comments"
    ).toHaveText("15", { message: "The first post should have 15 comments" });
    expect(
        ".o_social_stream_post_kanban_global:first-child .o_social_stream_post_facebook_stats > *:not(.o_social_facebook_likes):not(.o_social_facebook_comments)"
    ).toHaveText(`3\nShares\n18 Views`, {
        message: "The first post should have 3 shares and 18 'reach'",
    });
});

test("Check comments behavior", async () => {
    mockStatsRpc();
    onRpc("/social_facebook/like_comment", () => {
        expect.step("like_comment");
        return {};
    });
    onRpc("/social_facebook/get_comments", () => ({
        summary: { total_count: 1 },
        comments: [
            {
                from: {
                    id: 1,
                    picture: { data: { url: "socialtest/picture" } },
                },
                user_likes: false,
                message: "Root Comment",
                reactions: { LIKE: 3 },
                comments: {
                    data: [
                        {
                            from: {
                                id: 2,
                                picture: { data: { url: "socialtest/picture" } },
                            },
                            user_likes: true,
                            message: "Sub Comment 1",
                            reactions: { LIKE: 5 },
                        },
                        {
                            from: {
                                id: 3,
                                picture: { data: { url: "socialtest/picture" } },
                            },
                            user_likes: false,
                            message: "Sub Comment 2",
                            reactions: { LIKE: 10 },
                        },
                    ],
                },
            },
        ],
    }));
    onRpc("socialtest/picture", () => "");
    await mountView({
        type: "kanban",
        resModel: "social.stream.post",
    });
    await contains(".o_social_stream_post_facebook_stats .fa-comments").click();

    // 1. Root comment is displayed with 3 likes and 2 replies options.
    expect(
        ".o_social_comments_messages .o_social_comment_text:contains('Root Comment')"
    ).toHaveCount(1, { message: "Root comment should be displayed." });

    expect(
        ".o_social_comment_wrapper .o_social_comment_message:contains('View 2 replies')"
    ).toHaveCount(1, { message: "There are 2 replies below the root comment." });

    expect(".o_social_comment_wrapper .o_social_likes_count:contains('3')").toHaveCount(1, {
        message: "The root comment should have 3 likes",
    });

    // 2. Load replies and check display.
    await contains(".o_social_comment_wrapper span.o_social_comment_load_replies").click();

    expect(
        ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('Sub Comment 1')"
    ).toHaveCount(1, { message: "First sub comment should be loaded" });

    expect(
        ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('Sub Comment 2')"
    ).toHaveCount(1, { message: "Second sub comment should be loaded" });

    // 3. Check like/dislike behavior

    // 3a. Check like status and count
    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_comment_user_likes"
    ).toHaveCount(1, { message: "First comment is liked" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 2'):not(.o_social_comment_user_likes)"
    ).toHaveCount(1, { message: "Second comment is NOT liked" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_likes_count:contains('5')"
    ).toHaveCount(1, { message: "Sub comment 1 should have 5 likes" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_likes_count:contains('10')"
    ).toHaveCount(1, { message: "Sub comment 2 should have 10 likes" });

    // 3b. Dislike first and like second sub-comments
    const subComments = queryAll(".o_social_comment .o_social_comment");
    await contains(".o_social_comment_like", { root: subComments[0] }).click();
    expect.verifySteps(["like_comment"]);
    await contains(".o_social_comment_like", { root: subComments[1] }).click();
    expect.verifySteps(["like_comment"]);

    // 3a. Check like status and count now that it's reversed
    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 1'):not(.o_social_comment_user_likes)"
    ).toHaveCount(1, { message: "First comment is NOT liked" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_comment_user_likes"
    ).toHaveCount(1, { message: "Second comment is liked" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 1') .o_social_likes_count:contains('4')"
    ).toHaveCount(1, { message: "Sub comment 1 should have 4 likes" });

    expect(
        ".o_social_comment .o_social_comment:contains('Sub Comment 2') .o_social_likes_count:contains('11')"
    ).toHaveCount(1, { message: "Sub comment 2 should have 11 likes" });

    // 4. Add comment

    // Patch "addComment" to return new comment
    // Sadly 'XMLHttpRequest' cannot be mocked easily (would have been better)
    patchWithCleanup(StreamPostCommentsReply.prototype, {
        async _addComment(textarea) {
            const formData = new FormData(
                textarea.closest(".o_social_write_reply").querySelector("form")
            );
            this.props.onAddComment({
                from: {
                    id: 1,
                    picture: { data: { url: "socialtest/picture" } },
                },
                message: formData.get("message"),
                likes: { summary: { total_count: 3 } },
            });
        },
    });

    await contains(".o_social_write_reply .o_social_add_comment").edit("New Comment");
    await contains(".o_social_write_reply .o_social_add_comment").press("Enter");

    expect(
        ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('New Comment')"
    ).toHaveCount(1, { message: "New Comment should be displayed." });

    // 5. Add reply to comment
    await contains(".o_social_comment_wrapper span.o_social_comment_load_replies").click();
    await contains(".o_social_comment .o_social_comment .o_social_comment_reply").click();
    await contains(".o_social_comment .o_social_add_comment").edit("New Reply");
    await contains(".o_social_comment .o_social_add_comment").press("Enter");

    expect(
        ".o_social_comment_wrapper .o_social_comment_message div.o_social_comment_text:contains('New Reply')"
    ).toHaveCount(1, { message: "New Reply should be displayed" });
});
