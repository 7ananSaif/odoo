import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

import { Component, onWillStart, useState } from "@odoo/owl";

class Member {
    constructor(data) {
        Object.assign(this, data);
    }

    get avatarUrl() {
        return `/web/image/knowledge.article.member/${this.member_id}/article_member_avatar`;
    }

    get basedOnName() {
        return `${this.based_on_icon || "📄"} ${this.based_on_name || _t("Untitled")}`;
    }

    get canWrite() {
        return this.permission === "write";
    }

    get id() {
        return this.member_id;
    }

    get isCurrentUser() {
        return this.partner_id === user.partnerId;
    }

    get isRemovable() {
        return !(this.based_on && this.permission === "none");
    }
}

export class PermissionPanel extends Component {
    static template = "knowledge.PermissionPanel";
    static props = {
        reactiveRecordWrapper: Object,
        openArticle: Function,
        sendArticleToTrash: Function,
        close: Function,
    };
    static components = { Dropdown, DropdownItem };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ members: {}, isArticleLoaded: true });
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.mailStore = useService("mail.store");
        this.userIsAdmin = user.isAdmin;
        onWillStart(async () => (this.userIsInternal = await user.hasGroup("base.group_user")));
        onWillStart(async () => await this.loadMembers());
    }

    get record() {
        return this.props.reactiveRecordWrapper.record;
    }

    get hasUniqueWriter() {
        return (
            this.data.inherited_permission !== "write" &&
            this.members.filter((member) => member.permission === "write").length === 1
        );
    }

    get inheritedPermissionParent() {
        return {
            id: this.data.inherited_permission_parent_id.id,
            name: this.data.inherited_permission_parent_id.display_name || _t("Untitled"),
        };
    }

    get isRootArticle() {
        return !this.data.parent_id;
    }

    get parentArticle() {
        return {
            id: this.data.parent_id.id,
            name: this.data.parent_id.display_name,
        };
    }

    get visibility() {
        return this.data.is_article_visible_by_everyone ? "everyone" : "members";
    }

    get data() {
        return this.props.reactiveRecordWrapper.record.data;
    }

    get members() {
        return this.state.members;
    }

    get permissionLevel() {
        return { none: 0, read: 1, write: 2 };
    }

    get permissions() {
        return { none: _t("No Access"), read: _t("Can Read"), write: _t("Can Edit") };
    }

    get internalPermissions() {
        return { none: _t("Members only"), read: _t("Can Read"), write: _t("Can Edit") };
    }

    get userCanEdit() {
        return this.data.user_can_write;
    }

    get userIsInternalEditor() {
        return this.userIsAdmin || (this.userIsInternal && this.userCanEdit);
    }

    get visibilities() {
        return { everyone: _t("Everyone"), members: _t("Members only") };
    }

    /**
     * Loads the members displayed in the permissions panel.
     * If the user is included in the member list, they will be shown first,
     * followed by the other members in alphabetical order.
     * @param {integer} articleId
     */
    async loadMembers(articleId = this.record.resId) {
        const members = await this.orm.call(
            "knowledge.article",
            "get_permission_panel_members",
            [articleId]
        );
        this.state.members = members.map((memberVals) => {
            return new Member(memberVals);
        }).sort((m1, m2) => {
            if (m1.isCurrentUser || !m2.name) {
                return -1;
            }
            if (m2.isCurrentUser || !m1.name) {
                return 1;
            }
            return m1.name.localeCompare(m2.name);
        });
    }

    async load() {
        await Promise.all([this.loadMembers(), this.record.load()]);
    }

    /**
     * @param {String} permission
     */
    async setInternalPermission(permission) {
        await this.orm.call("knowledge.article", "set_internal_permission", [
            this.record.resId,
            permission,
        ]);
        await this.load();
    }

    async removeArticleMember(member) {
        await this.orm.call("knowledge.article", "remove_member", [this.record.resId, member.id]);
        //edge case: if the current user is removed from the article, we need to redirect to the home page
        if (
            member.isCurrentUser &&
            this.userIsInternal &&
            this.data.inherited_permission === "none" &&
            !this.userIsAdmin
        ) {
            this.actionService.doAction(
                await this.orm.call("knowledge.article", "action_home_page", [false]),
                { stackPosition: "replaceCurrentAction" }
            );
            return;
        }
        await this.load();
    }

    async restore() {
        await this.orm.call("knowledge.article", "restore_article_access", [this.record.resId]);
        await this.load();
    }

    /**
     * @param {String} visibility
     */
    async setInternalVisibility(visibility) {
        await this.orm.call("knowledge.article", "set_is_article_visible_by_everyone", [
            this.record.resId,
            visibility === "everyone",
        ]);
        await this.load();
    }

    async setMemberPermission(member, permission) {
        await this.orm.call("knowledge.article", "set_member_permission", [
            this.record.resId,
            member.id,
            permission,
        ]);
        await this.load();
    }

    openInviteDialog() {
        this.actionService.doAction("knowledge.knowledge_invite_action_from_article", {
            additionalContext: { active_id: this.record.resId },
            onClose: async () => await this.load(),
        });
    }

    /**
     * @param {Member} member
     */
    onMemberClick(member) {
        this.mailStore.openChat({ partnerId: member.partner_id });
    }

    /**
     * @param {number} resId
     */
    async openArticle(resId) {
        // Permission panel needs to stay open while switching articles.
        this.state.isArticleLoaded = false;
        await this.props.openArticle(resId);
        await this.loadMembers(resId);
        this.state.isArticleLoaded = true;
    }

    async restoreArticle() {
        this.dialog.add(ConfirmationDialog, {
            body: _t(
                "Are you sure you want to restore access? This means this article will now inherit any access set on its parent articles."
            ),
            cancel: () => {},
            cancelLabel: _t("Discard"),
            confirm: async () => {
                await this.restore();
            },
            confirmLabel: _t("Restore Access"),
            title: _t("Restore Access"),
        });
    }

    /**
     * @param {Member} member
     * @param {String} permission
     */
    async selectMemberPermission(member, permission) {
        if (permission === member.permission) {
            return;
        }
        if (member.isCurrentUser && !this.userIsAdmin) {
            if (permission === "none") {
                // setting own permission to none, user will leave the article
                this.dialog.add(ConfirmationDialog, {
                    cancel: () => {},
                    cancelLabel: _t("Discard"),
                    confirm: async () => {
                        await this.setMemberPermission(member, permission);
                        await this.actionService.doAction(
                            "knowledge.ir_actions_server_knowledge_home_page"
                        );
                    },
                    confirmLabel: _t("Lose Access"),
                    title: _t("Leave Article"),
                    body: _t(
                        'Are you sure you want to set your permission to "No Access"? If you do, you will no longer have access to the article.'
                    ),
                });
            } else {
                // downgrading own permission from write to read
                this.dialog.add(ConfirmationDialog, {
                    cancel: () => {},
                    cancelLabel: _t("Discard"),
                    confirm: async () => {
                        await this.setMemberPermission(member, permission);
                    },
                    confirmLabel: _t("Restrict own access"),
                    title: _t("Change Permission"),
                    body: _t('Are you sure you want to remove your own "Write" access?'),
                });
            }
        } else if (member.based_on) {
            // we are desyncing the article from its parent.
            this.dialog.add(ConfirmationDialog, {
                cancel: () => {},
                cancelLabel: _t("Discard"),
                confirm: async () => {
                    await this.setMemberPermission(member, permission);
                },
                confirmLabel: _t("Restrict Access"),
                title: _t("Change Permission"),
                body: _t(
                    "Are you sure you want to change the permission? This means it will no longer inherit access rights from its parent articles."
                ),
            });
        } else {
            // changing permission of non-inherited member or admin upgrading own permission
            await this.setMemberPermission(member, permission);
        }
    }

    async removeMember(member) {
        if (member.isCurrentUser && member.permission !== "none") {
            if (this.data.category === "private") {
                // leaving private article, article will be sent to trash
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Leave Private Article"),
                    body: _t(
                        "Are you sure you want to leave your private Article? As you are its last member, it will be moved to the Trash."
                    ),
                    cancel: () => {},
                    cancelLabel: _t("Discard"),
                    confirm: () => this.props.sendArticleToTrash(),
                    confirmLabel: _t("Move to Trash"),
                });
            } else {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Leave Article"),
                    body: _t(
                        "Are you sure you want to leave this article? That means losing your personal access to it."
                    ),
                    cancel: () => {},
                    cancelLabel: _t("Discard"),
                    confirm: async () => {
                        await this.removeArticleMember(member);
                    },
                    confirmLabel: _t("Leave Article"),
                });
            }
        } else if (member.based_on) {
            // removing inherited member permission, this will desync the article from its parent
            this.dialog.add(ConfirmationDialog, {
                title: _t("Restrict Access"),
                body: _t(
                    "Are you sure you want to restrict access to this article? This means that it will no longer inherit access rights from its parents."
                ),
                confirm: async () => {
                    await this.removeArticleMember(member);
                },
                confirmLabel: _t("Restrict Access"),
            });
        } else {
            await this.removeArticleMember(member);
        }
    }

    async selectInternalPermission(permission) {
        if (permission === this.data.inherited_permission) {
            return;
        }
        if (
            this.data.inherited_permission_parent_id &&
            this.permissionLevel[permission] < this.permissionLevel[this.data.inherited_permission]
        ) {
            this.dialog.add(ConfirmationDialog, {
                cancel: () => {},
                cancelLabel: _t("Discard"),
                confirm: async () => {
                    await this.setInternalPermission(permission);
                },
                title: _t("Restrict Access"),
                confirmLabel: _t("Restrict Access"),
                body: _t(
                    "Are you sure you want to restrict access to this article? This means it will no longer inherit access rights from its parents."
                ),
            });
        } else {
            await this.setInternalPermission(permission);
        }
    }

    async selectInternalVisibility(visibility) {
        if (visibility === this.visibility) {
            return;
        }
        await this.setInternalVisibility(visibility);
    }
}
