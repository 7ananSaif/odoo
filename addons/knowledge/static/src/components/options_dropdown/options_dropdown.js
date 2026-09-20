import { HistoryDialog } from "@html_editor/components/history_dialog/history_dialog";
import { READONLY_MAIN_EMBEDDINGS } from "@html_editor/others/embedded_components/embedding_sets";
import { useOpenChat } from "@mail/core/web/open_chat_hook";
import MoveArticleDialog from "@knowledge/components/move_article_dialog/move_article_dialog";
import { KNOWLEDGE_READONLY_EMBEDDINGS } from "@knowledge/editor/embedded_components/embedding_sets";
import { getRandomIcon } from "@knowledge/js/knowledge_utils";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

import { Component, onWillStart, useState } from "@odoo/owl";

export class OptionsDropdown extends Component {
    static components = { Dropdown, DropdownItem };
    static template = "knowledge.OptionsDropdown";
    static props = {
        record: { type: Object },
    };

    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.openChat = useOpenChat("res.users");
        this.formatDateTime = formatDateTime;
        this.commentsState = useState(this.env.commentsState);
        this.chatterPanelState = useState(this.env.chatterPanelState);
        this.propertiesPanelState = useState(this.env.propertiesPanelState);
        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
            this.canCreateArticle = await user.checkAccessRight("knowledge.article", "create");
        });
    }

    get articleId() {
        return this.props.record.resId;
    }

    get creationDate() {
        return this.data.create_date;
    }

    get creator() {
        return this.data.create_uid.display_name;
    }

    get data() {
        return this.props.record.data;
    }

    get lastEditionDate() {
        return this.data.last_edition_date;
    }

    get lastEditor() {
        return this.data.last_edition_uid.display_name;
    }

    get lastEditorAvatarUrl() {
        return `/web/image/knowledge.article/${this.articleId}/last_edition_user_avatar`;
    }

    async addCover() {
        let res;
        try {
            res = await rpc(`/knowledge/article/${this.articleId}/add_random_cover`, {
                query: this.props.record.data.name,
                orientation: "landscape",
            });
        } catch (e) {
            console.error(e);
        }
        if (res?.cover_id) {
            await this.props.record.update({ cover_image_id: { id: res.cover_id } });
        } else {
            this.env.openCoverSelector();
        }
    }

    async addIcon() {
        await this.props.record.update({ icon: await getRandomIcon() });
    }

    async beforeOpen() {
        await this.props.record.save();
    }

    async copy() {
        await this.props.record.save();
        const [articleId] = await this.orm.call("knowledge.article", "action_make_copy", [
            this.articleId,
        ]);
        this.env.openArticle(articleId);
    }

    export() {
        // Use the browser print as wkhtmltopdf sadly does not handle emojis / embed views / ...
        // (Investigation shows that it would be complicated to add that support).
        window.print();
    }

    moveArticle() {
        this.dialog.add(MoveArticleDialog, { knowledgeArticleRecord: this.props.record });
    }

    onCreatorClick() {
        this.openChat(this.data.create_uid.id);
    }

    onLastEditorClick() {
        this.openChat(this.data.last_edition_uid.id);
    }

    async openHistory() {
        const [{ html_field_history_metadata: metaData }] = await this.orm.read(
            "knowledge.article",
            [this.articleId],
            ["html_field_history_metadata"]
        );
        if (!metaData.body) {
            return;
        }
        this.dialog.add(HistoryDialog, {
            recordId: this.articleId,
            recordModel: "knowledge.article",
            versionedFieldName: "body",
            historyMetadata: metaData.body,
            restoreRequested: (html, close) => {
                this.props.record.update({ body: html });
                close();
            },
            embeddedComponents: [...READONLY_MAIN_EMBEDDINGS, ...KNOWLEDGE_READONLY_EMBEDDINGS],
        });
    }

    removeIcon() {
        this.props.record.update({ icon: false });
    }

    removeCover() {
        this.props.record.update({ cover_image_id: false });
    }

    sendToTrash() {
        this.env.sendArticleToTrash();
    }

    toggleFullWidth() {
        this.props.record.update({ full_width: !this.props.record.data.full_width });
        // For calendar view to resize.
        browser.dispatchEvent(new Event("resize"));
    }

    async toggleIsListedInTemplatesGallery() {
        const newVal = !this.data.is_listed_in_templates_gallery;
        await this.orm.write("knowledge.article", [this.props.record.resId], {
            is_listed_in_templates_gallery: newVal,
        });
        this.notification.add(
            newVal
                ? _t("Article added to the list of Templates")
                : _t("Article removed from the list of Templates"),
            { type: "success" }
        );
    }

    toggleItem() {
        this.props.record.update(
            { is_article_item: !this.props.record.data.is_article_item },
            { save: true }
        );
    }

    async toggleLock() {
        await this.props.record.save();
        await this.orm.call("knowledge.article", "action_set_lock", [this.articleId], {
            lock: !this.props.record.data.is_locked,
        });
        await this.props.record.load();
    }

    async unarchive() {
        await this.orm.call("knowledge.article", "action_unarchive", [this.articleId]);
        await this.props.record.load();
    }
}
