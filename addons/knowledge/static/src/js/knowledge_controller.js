import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { _t } from "@web/core/l10n/translation";
import { FormController } from '@web/views/form/form_controller';
import { KnowledgeCoverDialog } from '@knowledge/components/knowledge_cover/knowledge_cover_dialog';
import { KnowledgeSidebar } from '@knowledge/components/sidebar/sidebar';
import { useBus, useService } from "@web/core/utils/hooks";

import {
    onWillStart,
    reactive,
    useSubEnv,
    useEffect,
    useExternalListener,
    useRef,
} from "@odoo/owl";
import { ArticleAnnexePickerDialog } from "@knowledge/components/article_annexe_picker_dialog/article_annexe_picker_dialog";

export class KnowledgeArticleFormController extends FormController {
    static template = "knowledge.ArticleFormView";
    static components = {
        ...FormController.components,
        KnowledgeSidebar,
    };

    setup() {
        super.setup();
        this.root = useRef('root');
        this.orm = useService('orm');
        this.actionService = useService('action');
        this.dialogService = useService("dialog");
        this.commentsService = useService("knowledge.comments");

        useSubEnv({
            createArticle: this.createArticle.bind(this),
            ensureArticleName: this.ensureArticleName.bind(this),
            openArticle: this.openArticle.bind(this),
            openCoverSelector: this.openCoverSelector.bind(this),
            renameArticle: this.renameArticle.bind(this),
            sendArticleToTrash: this.sendArticleToTrash.bind(this),
            toggleAsideMobile: this.toggleAsideMobile.bind(this),
            toggleChatter: this.toggleChatter.bind(this),
            toggleComments: this.toggleComments.bind(this),
            toggleFavorite: this.toggleFavorite.bind(this),
            toggleProperties: this.toggleProperties.bind(this),
            save: this.save.bind(this),
            discard: this.discard.bind(this),
            // Internal states:
            propertiesPanelState: reactive({ isDisplayed: false }),
            chatterPanelState: reactive({ isDisplayed: false }),
            commentsState: this.commentsService.getCommentsState(),
        });

        useBus(this.env.bus, 'KNOWLEDGE:OPEN_ARTICLE', (event) => {
            this.openArticle(event.detail.id);
        });

        useBus(this.env.bus, "KNOWLEDGE:OPEN_ANNEXE_TEMPLATE_PICKER", async (event) => {
            const props = event.detail;
            this.dialogService.add(ArticleAnnexePickerDialog, props);
        });

        // Unregister the current candidate recordInfo for Knowledge macros in
        // case of breadcrumbs mismatch.
        onWillStart(() => {
            if (
                !this.env.inDialog &&
                this.env.config.breadcrumbs &&
                this.env.config.breadcrumbs.length
            ) {
                // Unregister the current candidate recordInfo in case of
                // breadcrumbs mismatch.
                this.knowledgeCommandsService.unregisterCommandsRecordInfo(this.env.config.breadcrumbs);
            }
        });

        useExternalListener(document.documentElement, 'mouseleave', async () => {
            if (await this.model.root.isDirty()) {
                await this.model.root.save();
            }
        });

        useEffect(
            () => {
                const scrollView = this.root.el?.querySelector(".o_scroll_view_lg");
                if (scrollView) {
                    scrollView.scrollTop = 0;
                }
                const mobileScrollView = this.root.el?.querySelector(".o_knowledge_main_view");
                if (mobileScrollView) {
                    mobileScrollView.scrollTop = 0;
                }
            },
            () => [this.model.root.resId]
        );

        useExternalListener(window, "keydown", async event => {
            const hotkey = getActiveHotkey(event);
            if (hotkey === "control+s") {
                event.preventDefault();
                if (this.model.root.dirty) {
                    await this.save({ reload: false });
                }
            }
        });
    }

    /**
     * Ensure that the title is set @see beforeUnload
     * Dirty check is sometimes necessary in cases where the user leaves
     * the article from inside an article (i.e. embedded views/links) very
     * shortly after a mutation (i.e. in tours). At that point, the
     * html_field may not have notified the model from the change.
     * @override
     */
    async beforeLeave() {
        if (this.model.root.resId) {
            await this.ensureArticleName();
        }
        await this.model.root.isDirty();
        return super.beforeLeave();
    }

    /**
     * Check that the title is set or not before closing the tab and
     * save the whole article, if the current article exists (it does
     * not exist if there are no articles to show, in which case the no
     * content helper is displayed).
     * @override
     */
    async beforeUnload(ev) {
        if (this.model.root.resId) {
            await this.ensureArticleName();
            if (await this.model.root.isDirty()) {
                await super.beforeUnload(ev); // triggers an urgent save
            }
        }
    }

    /**
     * If the article has no name set, tries to rename it.
     */
    ensureArticleName() {
        const recordData = this.model.root.data;
        if (
            !recordData.name &&
            !(recordData.is_locked || !recordData.user_can_write || !recordData.active)
        ) {
            return this.renameArticle();
        }
    }

    get resId() {
        return this.model.root.resId;
    }

    /**
     * Create a new article and open it.
     * @param {String} category - Category of the new article
     * @param {integer} targetParentId - Id of the parent of the new article (optional)
     */
    async createArticle(category, targetParentId) {
        const articleIds = await this.orm.call(
            "knowledge.article",
            "article_create",
            [],
            {
                is_private: category === 'private',
                parent_id: targetParentId ? targetParentId : false
            }
        );
        this.openArticle(articleIds[0]);
    }

    getHtmlTitle() {
        const titleEl = this.root.el.querySelector(".note-editable.odoo-editor-editable h1");
        if (titleEl) {
            const title = titleEl.textContent.trim();
            if (title) {
                return title;
            }
        }
    }

    displayName() {
        return this.model.root.data.name || _t("New");
    }

    /**
     * Callback executed before the record save (if the record is valid).
     * When an article has no name set, use the title (first h1 in the
     * body) to try to save the article with a name.
     * @overwrite
     */
    async onWillSaveRecord(record, changes) {
        if (!record.data.name) {
            const title = this.getHtmlTitle();
            if (title) {
                changes.name = title;
            }
         }
    }

    /**
     * @param {integer} - resId: id of the article to open
     */
    async openArticle(resId) {
        if (!resId || resId === this.resId) {
            return;
        }

        // blur to remove focus on the active element
        document.activeElement.blur();

        // load the new record
        try {
            if (this.model.root.isNew) {
                await this.model.load({ resId });
            } else {
                await this.ensureArticleName();
                if (await this.model.root.isDirty()) {
                    await this.model.root.save({
                        onError: (error, options) => this.onSaveError(error, options, true),
                        nextId: resId,
                    });
                } else {
                    await this.model.load({ resId });
                }
            }
        } catch {
            this.dialogService.add(AlertDialog, {
                title: _t("Access Denied"),
                body: _t(
                    "The article you are trying to open has either been removed or is inaccessible.",
                ),
                confirmLabel: _t("Close"),
            });
            return false;
        }
        this.toggleAsideMobile(false);
        return true;
    }

    openCoverSelector() {
        this.dialogService.add(KnowledgeCoverDialog, {
            articleCoverId: this.model.root.data.cover_image_id.id,
            articleName: this.model.root.data.name || "",
            save: (id) => this.model.root.update({
                cover_image_id: { id }
            })
        });
    }

    /**
     * Rename the article using the given name, or using the article title if
     * no name is given (first h1 in the body). If no title is found, the
     * article is kept untitled.
     * @param {string} name - new name of the article
     */
    renameArticle(name) {
        if (!name) {
            const title = this.getHtmlTitle();
            if (!title) {
                return;
            }
            name = title;
        }
        return this.model.root.update({ name });
    }

    async sendArticleToTrash() {
        await this.orm.call("knowledge.article", "action_send_to_trash", [this.resId]);
        await this.actionService.doAction(
            await this.orm.call("knowledge.article", "action_redirect_to_parent", [this.resId]),
            { stackPosition: "replaceCurrentAction" },
        );
    }

    /**
     * Toggle the aside menu on mobile devices (< 576px).
     * @param {boolean} force
     */
    toggleAsideMobile(force) {
        const container = this.root.el.querySelector('.o_knowledge_form_view');
        container.classList.toggle('o_toggle_aside', force);
    }

    toggleChatter() {
        this.env.chatterPanelState.isDisplayed = !this.env.chatterPanelState.isDisplayed;
    }

    toggleComments() {
        if (this.env.commentsState.displayMode === "handler") {
            this.env.commentsState.displayMode = "panel";
        } else {
            this.env.commentsState.displayMode = "handler";
        }
    }

    /**
     * Add/Remove article from favorites and reload the favorite tree.
     * One does not use "record.update" since the article could be in readonly.
     * @param {event} Event
     */
    async toggleFavorite(event) {
        // Save in case name has been edited, so that this new name is used
        // when adding the article in the favorite section.
        if (await this.model.root.isDirty()) {
            await this.model.root.save();
        }
        await this.orm.call(this.model.root.resModel, "action_toggle_favorite", [[this.resId]]);
        // Load to have the correct value for 'is_user_favorite'.
        await this.model.root.load();
    }

    /**
     * Toggle the properties panel
     * @param {boolean} [force] - Flag determining the desired visibility of the properties panel.
     */
    toggleProperties(force) {
        this.env.propertiesPanelState.isDisplayed = (
            typeof force === "boolean" ? force : !this.env.propertiesPanelState.isDisplayed
        );
    }
}
