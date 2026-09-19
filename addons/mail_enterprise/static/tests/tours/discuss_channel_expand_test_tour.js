import { registry } from "@web/core/registry";

/**
 * This tour depends on data created by python test in charge of launching it.
 * It is not intended to work when launched from interface. It is needed to test
 * an action (action manager) which is not possible to test with QUnit.
 * @see mail_enterprise/tests/test_discuss_channel_expand.py
 */
registry
    .category("web_tour.tours")
    .add("mail_enterprise/static/tests/tours/discuss_channel_expand_test_tour.js", {
        url: "/odoo",
        steps: () => [
            {
                trigger: ".o-mail-DiscussSystray-class .fa-comments",
                run: "click",
            },
            {
                trigger: ".o-mail-NotificationItem:contains('test-mail-channel-expand-tour')",
                run: "click",
            },
            {
                trigger:
                    '.o-mail-ChatWindow:contains("test-mail-channel-expand-tour") [title="Open Actions Menu"]',
                run: "click",
            },
            {
                trigger: '.o-dropdown-item:contains("Open in Discuss")',
                run: "click",
            },
            {
                content:
                    "Check that first message of #test-mail-channel-expand-tour is shown in Discuss app",
                trigger:
                    '.o-mail-DiscussContent .o-mail-Message-body:contains("test-message-mail-channel-expand-tour")',
            },
        ],
    });
