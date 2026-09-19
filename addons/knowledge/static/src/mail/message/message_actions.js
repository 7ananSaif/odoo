import { _t } from "@web/core/l10n/translation";
import { registerMessageAction } from "@mail/core/common/message_actions";

registerMessageAction("closeThread", {
    condition: ({ owner }) => owner.env.closeThread && !owner.env.isResolved(),
    icon: "fa fa-check",
    name: _t("Mark the discussion as resolved"),
    onSelected: ({ owner }) => owner.env.closeThread(),
    sequence: 0,
});

registerMessageAction("openThread", {
    condition: ({ owner }) => owner.env.openThread && owner.env.isResolved(),
    icon: "fa fa-retweet",
    name: _t("Re-open the discussion"),
    onSelected: ({ owner }) => owner.env.openThread(),
    sequence: 0,
});
