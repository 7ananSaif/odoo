import { expect, test } from "@odoo/hoot";
import { queryOne } from "@odoo/hoot-dom";

import { defineModels, models, mountView } from "@web/../tests/web_test_helpers";

import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class SocialPostTemplate extends models.ServerModel {
    _name = "social.post.template";
    _records = [
        {
            id: 1,
            message: "Hello @Odoo-Social, check this out: https://www.odoo.com #crazydeals #odoo",
            twitter_message:
                "Hello @Odoo-Social, check this out: https://www.odoo.com #crazydeals #odoo",
            is_split_per_media: false,
            has_twitter_account: true,
            twitter_preview: `
            <div class="o_social_preview o_social_twitter_preview bg-white border rounded overflow-hidden w-100">
                <div class="w-75 d-flex m-3">
                    <span class="o_social_preview_icon_wrapper overflow-hidden me-2">
                        <i class="fa fa-twitter fa-2x"></i>
                    </span>
                    <div class="o_social_preview_header">
                        <b class="text-900">X Account</b>
                        <span class="text-600">@x ·
                            11m
                        </span>
                    </div>
                </div>
                <div class="d-table w-75 pb-3 mx-3">
                    <span class="o_social_preview_message">Hello <a href="https://twitter.com/Odoo-Social" target="_blank" rel="noreferrer">@Odoo-Social</a>, check this out: <a href="https://www.odoo.com" class="text-truncate" target="_blank" rel="noreferrer">https://www.odoo.com</a> <a href="https://twitter.com/hashtag/crazydeals?src=hash" target="_blank" rel="noreferrer">#crazydeals</a> <a href="https://twitter.com/hashtag/odoo?src=hash" target="_blank" rel="noreferrer">#odoo</a></span>
                </div>
                <a target="_blank" href="https://www.odoo.com" rel="noreferrer">
                    <div class="o_social_stream_post_image d-flex overflow-hidden                         o_social_stream_post_image_clickable">
                            <div class="w-100">
                                <img alt="Post Image" src="https://www.odoo.com/web/image/54404732-3d9bec26/SPI_homepage.png">
                            </div>
                    </div>
                    <div class="o_social_twitter_preview_article w-100 pb-1 d-block text-white">
                        <small class="p-1 mx-2 rounded">www.odoo.com</small>
                    </div>
                </a>
            </div>`,
        },
    ];

    _views = {
        form: `
            <form string="Social Post Template" class="o_social_post_view_form">
                <sheet>
                    <group>
                        <group string="Your Post" name="social_post_global" class="o_social_post_form_content">
                            <field name="is_split_per_media" invisible="1"/>
                            <field name="twitter_message" invisible="1"/>
                            <field name="twitter_preview" widget="social_post_preview" media_type="twitter" readonly="1"/>
                        </group>
                    </group>
                </sheet>
            </form>
        `,
    };
}
defineMailModels();
defineModels([SocialPostTemplate]);

test("SocialPostFormatterMixin on HtmlField is working as expected", async () => {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "social.post.template",
    });
    const htmlValue = queryOne(".o_social_preview_message").innerHTML;

    expect(htmlValue).toEqual(
        [
            `Hello`,
            `<a href="https://twitter.com/Odoo-Social" target="_blank">@Odoo-Social</a>,`,
            `check this out:`,
            `<a href="https://www.odoo.com" class="text-truncate" target="_blank" rel="noreferrer noopener">https://www.odoo.com</a>`,
            `<a href="https://twitter.com/hashtag/crazydeals?src=hash" target="_blank">#crazydeals</a>`,
            `<a href="https://twitter.com/hashtag/odoo?src=hash" target="_blank">#odoo</a>`,
        ].join(" ")
    );
});
