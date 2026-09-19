import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { knowledgeTopbar } from "@knowledge/components/topbar/topbar";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    defineActions,
    defineModels,
    fields,
    makeMockEnv,
    makeMockServer,
    mockService,
    models,
    mountView,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { user } from "@web/core/user";

import { beforeEach, expect, test } from "@odoo/hoot";
import { click, queryText } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { mockKnowledgePermissionPanelRpc } from "./knowledge_test_helpers";

const permissions = {
    none: "No Access",
    read: "Can Read",
    write: "Can Edit",
};
const internalPermissions = {
    none: "Members only",
    read: "Can Read",
    write: "Can Edit",
};

const permLvl = {
    none: 0,
    read: 1,
    write: 2,
};

let members = [];

class KnowledgeArticle extends models.ServerModel {
    _name = "knowledge.article";

    name = fields.Char();
    active = fields.Boolean({ default: true });
    icon = fields.Char();
    parent_path = fields.Char();
    parent_id = fields.Many2one({ relation: "knowledge.article" });
    root_article_id = fields.Many2one({ relation: "knowledge.article" });
    category = fields.Selection({ selection: ["private", "workspace", "shared"] });
    is_article_visible_by_everyone = fields.Boolean();
    is_desynchronized = fields.Boolean();
    internal_permission = fields.Selection({ selection: Object.keys(internalPermissions) });
    inherited_permission_parent_id = fields.Many2one({ relation: "knowledge.article" });
    inherited_permission = fields.Selection({ selection: Object.keys(internalPermissions) });
    user_can_write = fields.Boolean({ compute: "_compute_user_can_write" });
    user_permission = fields.Selection({ selection: Object.keys(permissions) });

    _records = [
        {
            id: 1,
            name: "Private Article",
            icon: "⛔️",
            parent_id: false,
            category: "private",
            is_article_visible_by_everyone: false,
            is_desynchronized: false,
            internal_permission: "none",
            inherited_permission_parent_id: false,
            inherited_permission: "none",
            user_permission: "write",
        },
        {
            id: 2,
            name: "Readonly Article",
            icon: "🚷",
            parent_id: false,
            category: "workspace",
            is_article_visible_by_everyone: false,
            is_desynchronized: false,
            internal_permission: "read",
            inherited_permission_parent_id: false,
            inherited_permission: "read",
            user_permission: "read",
        },
        {
            id: 3,
            name: "Shared Article",
            icon: "👥",
            parent_id: false,
            category: "shared",
            is_article_visible_by_everyone: false,
            is_desynchronized: false,
            internal_permission: "none",
            inherited_permission_parent_id: false,
            inherited_permission: "none",
            user_permission: "write",
        },
        {
            id: 4,
            name: "Workspace Article",
            icon: "👨‍💻",
            parent_id: false,
            category: "workspace",
            is_article_visible_by_everyone: true,
            is_desynchronized: false,
            internal_permission: "write",
            inherited_permission_parent_id: false,
            inherited_permission: "write",
            user_permission: "write",
        },
        {
            id: 5,
            name: "Workspace Child Article",
            icon: "",
            parent_id: 4,
            category: "workspace",
            is_article_visible_by_everyone: true,
            is_desynchronized: false,
            internal_permission: false,
            inherited_permission_parent_id: 4,
            inherited_permission: "write",
            user_permission: "write",
        },
        {
            id: 6,
            name: "Desynced Child Article",
            icon: "",
            parent_id: 4,
            category: "workspace",
            is_article_visible_by_everyone: true,
            is_desynchronized: true,
            internal_permission: "read",
            inherited_permission_parent_id: false,
            inherited_permission: "read",
            user_permission: "write",
        },
    ];

    _views = {
        form: '<form><widget name="knowledge_topbar"/></form>',
    };

    _compute_display_name() {
        for (const record of this) {
            record.display_name = record.icon + record.name;
        }
    }

    async _compute_user_can_write() {
        for (const record of this) {
            record.user_can_write =
                user.isAdmin ||
                record.user_permission === "write" ||
                members.some(
                    (member) =>
                        member.partner_id === serverState.partnerId && member.permission === "write"
                );
        }
    }

    get_permission_panel_members(id) {
        // should define members array in each test as members model is not defined for simplicity
        return members;
    }

    restore_article_access(id) {
        this.write(id, {
            is_desynchronized: false,
            inherited_permission_parent_id: 4,
            internal_permission: false,
            inherited_permission: "write",
        });
    }

    set_internal_permission(id, permission) {
        this.write(id, { internal_permission: permission, inherited_permission: permission });
    }

    set_is_article_visible_by_everyone(id, visibility) {
        this.write(id, { is_article_visible_by_everyone: visibility });
    }

    set_member_permission(id, memberId, permission) {
        const member = members.find((member) => member.member_id === memberId);
        if (!member) {
            return;
        }
        if (member.based_on && permLvl[permission] < permLvl[member.permission]) {
            this.write(id, { is_desynchronized: true });
            Object.assign(member, { based_on: false, based_on_icon: false, based_on_name: false });
        }
        Object.assign(member, { permission });
    }

    remove_member(id, memberId) {
        const index = members.findIndex((member) => member.member_id === memberId);
        if (index !== -1) {
            // test cases removing (non) inherited member
            if (id === 5) {
                if (members[index].based_on) {
                    this.write(id, { is_desynchronized: true });
                } else {
                    Object.assign(members[index], {
                        based_on: true,
                        based_on_name: "Workspace Article",
                        based_on_icon: "👨‍💻",
                        permission: "write",
                    });
                    return;
                }
            }
            members.splice(index, 1);
        }
    }

    action_send_to_trash() {
        expect.step("trash");
    }

    action_redirect_to_parent() {
        return { action: "redirect to parent" };
    }

    has_access = function () {
        return Promise.resolve(true);
    };
}

defineMailModels();
defineModels([KnowledgeArticle]);
// dummy action to mock the invite dialog
defineActions([
    {
        id: 99,
        xml_id: "knowledge.knowledge_invite_action_from_article",
        name: "Invite",
        res_model: "knowledge.article",
        target: "new",
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    },
]);

const internalPermissionSelector = ".o_internal_permission .dropdown-toggle";
const internalVisibilitySelector = ".o_internal_visibility .dropdown-toggle";
const inviteMemberSelector = ".fa-user-plus + .input-group";

const expectMember = (member, disabled) => {
    const selector = `.o_knowledge_permission_panel_members > div:contains(${member.name})`;
    const texts = [member.name];
    if (member.partner_share) {
        texts.push(member.partner_id === serverState.partnerId ? "(You)" : "(Guest)");
    }
    texts.push(member.email);
    if (member.based_on) {
        texts.push(`Based on ${member.based_on_icon} ${member.based_on_name}`);
    }
    texts.push(permissions[member.permission]);
    expect(queryText(selector).split("\n")).toEqual(texts);
    if (disabled) {
        expect(selector + " .dropdown-toggle").toHaveClass("disabled");
    } else {
        expect(selector + " .dropdown-toggle").not.toHaveClass("disabled");
    }
};

patchWithCleanup(knowledgeTopbar, {
    fieldDependencies: Object.entries(KnowledgeArticle._fields).map(([fieldName, field]) => ({
        name: fieldName,
        type: field.type,
    })),
});

let mockServer;
beforeEach(async () => {
    mockServer = await makeMockServer();
    await makeMockEnv({
        /** @param {integer} articleId */
        async openArticle(articleId) {
            expect.step(`open ${articleId}`);
            await this.reactiveRecordWrapper.record.model.load({ resId: articleId });
        },
        sendArticleToTrash() {
            expect.step("send to trash");
        },
        save: () => {},
        discard: () => {},
        commentsState: { isDisplayed: false },
        chatterPanelState: { isDisplayed: false },
        propertiesPanelState: { isDisplayed: true },
    });
    patchWithCleanup(PermissionPanel.prototype, {
        load() {
            expect.step("reload record");
            return super.load();
        },
    });
});

async function mountPermissionPanel(articleId, user_can_write = undefined) {
    if (user_can_write !== undefined) {
        mockServer.env["knowledge.article"].write(articleId, { user_can_write });
    }
    await mountView({
        resId: articleId,
        resModel: "knowledge.article",
        type: "form",
        arch: KnowledgeArticle._views.form,
    });
    await click("button[data-hotkey='shift+s']");
    await animationFrame();
}

mockKnowledgePermissionPanelRpc();

test.tags("desktop");
test("Permission Panel as a read only user", async () => {
    patchWithCleanup(user, { isAdmin: false }); // readonly internal user
    members = [
        {
            member_id: 1,
            name: "current",
            email: "current@example.com",
            permission: "read",
            partner_id: serverState.partnerId,
            partner_share: true,
        },
        {
            member_id: 2,
            name: "alice",
            email: "alice@example.com",
            permission: "write",
        },
    ];
    await mountPermissionPanel(2, false);
    await animationFrame();
    // internal permission, visibility and members should appear as disabled
    expect(internalPermissionSelector).toHaveText("Can Read");
    expect(internalPermissionSelector).toHaveClass("disabled");
    expect(internalVisibilitySelector).toHaveText("Members only");
    expect(internalVisibilitySelector).toHaveClass("disabled");
    // since there is no right escalation in this case, the user can remove its member.
    expectMember(members[0], false);
    // invite input should not be shown
    expect(inviteMemberSelector).toHaveCount(0);
});

test.tags("desktop");
test("Permission Panel as a portal user", async () => {
    patchWithCleanup(user, { isAdmin: false, hasGroup: (group) => group !== "base.group_user" }); // portal user
    members = [
        {
            member_id: 1,
            name: "portal",
            email: "portal@example.com",
            partner_share: true,
            based_on: true,
            based_on_name: "Parent Article",
            based_on_icon: "👨‍💻",
            permission: "write",
        },
        {
            member_id: 2,
            name: "shrek",
            email: "shrek@example.com",
            permission: "write",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    // internal permission panel is not shown
    expect(internalPermissionSelector).toHaveCount(0);
    expect(internalVisibilitySelector).toHaveCount(0);
    // invitation input is not shown
    expect(inviteMemberSelector).toHaveCount(0);
    // members are shown with a disabled permission selector
    expect(".o_knowledge_permission_panel_members > div").toHaveCount(2);
    expectMember(members[0], true);
    expectMember(members[1], true);
});

test.tags("desktop");
test("Add a read member on a private article", async () => {
    members = [
        {
            member_id: 1,
            name: "user1",
            email: "user1@example.com",
            permission: "write",
        },
    ];
    await mountPermissionPanel(1, true);
    expect(internalPermissionSelector).toHaveText("Members only");
    expect(internalVisibilitySelector).toHaveCount(0);
    expect(".o_knowledge_permission_panel_members > div").toHaveCount(1);
    // member should be disabled: admin can't remove the editor of another users' private article)
    expectMember(members[0], true);
    await click(inviteMemberSelector);
    members.push({
        member_id: 2,
        name: "invited user",
        email: "invited@example.com",
        permission: "read",
    });
    await animationFrame();
    await click(".modal-header .btn-close");
    await animationFrame();
    // internal visibility should remain hidden as article is shared
    expect(internalVisibilitySelector).toHaveCount(0);
    // new member should be shown with the right permission
    expectMember(members[1]);
    // writer should not be able to change its permission as a writer is always required on an article
    expectMember(members[0], true);
    expect.verifySteps(["reload record"]);
});

test.tags("desktop");
test("Remove a member", async () => {
    members = [
        {
            member_id: 1,
            name: "bob",
            email: "bob@example.com",
            permission: "write",
        },
        {
            member_id: 2,
            name: "alice",
            email: "alice@example.com",
            permission: "write",
        },
    ];
    await mountPermissionPanel(3, true);
    await animationFrame();
    expect(".o_knowledge_permission_panel_members > div").toHaveCount(2);
    await click(".o_knowledge_permission_panel_members > div:first-child .dropdown-toggle");
    await animationFrame();
    expect(".o_knowledge_permission_panel_remove_member").toHaveText("Remove");
    await click(".o_knowledge_permission_panel_remove_member");
    await animationFrame();
    expect(".o_knowledge_permission_panel_members > div").toHaveCount(1);
    expect.verifySteps(["remove member 2 on article 3", "reload record"]);
});

test.tags("desktop");
test("Leave a private article", async () => {
    members = [
        {
            member_id: 1,
            name: "admin",
            email: "admin@example.com",
            permission: "write",
            partner_id: serverState.partnerId,
            partner_share: true,
        },
    ];
    await mountPermissionPanel(1, true);
    await animationFrame();
    await click(".o_knowledge_permission_panel_members .dropdown-toggle");
    await animationFrame();
    expect(".o_knowledge_permission_panel_remove_member").toHaveCount(1);
    expect(".o_knowledge_permission_panel_remove_member").toHaveText("Leave");
    await click(".o_knowledge_permission_panel_remove_member");
    await animationFrame();
    expect(".modal-title").toHaveText("Leave Private Article");
    await click(".modal-footer button:contains('Move to Trash')");
    await animationFrame();
    expect.verifySteps(["send to trash"]);
});

test.tags("desktop");
test("Change internal permission and visibility", async () => {
    members = [];
    await mountPermissionPanel(1, true);
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Members only");
    expect(internalVisibilitySelector).toHaveCount(0);
    await click(internalPermissionSelector);
    await animationFrame();
    await click(".o-dropdown-item:contains('Can Edit')");
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Can Edit");
    expect(internalVisibilitySelector).toHaveText("Members only");
    expect.verifySteps(["change permission to write on article 1", "reload record"]);
    await click(internalVisibilitySelector);
    await animationFrame();
    await click(".o-dropdown-item:contains('Everyone')");
    await animationFrame();
    expect(internalVisibilitySelector).toHaveText("Everyone");
    expect.verifySteps(["change visibility to everyone on article 1", "reload record"]);
});

test.tags("desktop");
test("Change inherited internal permission", async () => {
    members = [];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Can Edit");
    // child articles do not have the visibility option
    expect(internalVisibilitySelector).toHaveCount(0);
    expect(".knowledge_internal_permission_based_on_text").toHaveText(
        "Based on 👨‍💻Workspace Article"
    );
    await click(internalPermissionSelector);
    await animationFrame();
    await click(".o-dropdown-item:contains('Members only')");
    await animationFrame();
    // downgrading internal permission should show confirmation dialog
    expect(".modal-title").toHaveText("Restrict Access");
    await click(".modal-footer button:contains('Restrict access')");
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Members only");
    expect.verifySteps(["change permission to none on article 5", "reload record"]);
    // for simplicity the test model does not desync the article from its parent when changing the
    // permission, so we can check the behavior when upgrading the permission of a synced article
    // in the same test
    await click(internalPermissionSelector);
    await animationFrame();
    await click(".o-dropdown-item:contains('Can Read')");
    // upgrading internal permission of synced article should not show confirmation modal
    await animationFrame();
    expect(".modal-title").toHaveCount(0);
    expect(internalPermissionSelector).toHaveText("Can Read");
    expect.verifySteps(["change permission to read on article 5", "reload record"]);
});

test.tags("desktop");
test("Downgrade inherited member permission", async () => {
    members = [
        {
            member_id: 1,
            name: "inherited",
            email: "inherited@example.com",
            based_on: true,
            based_on_name: "Parent Article",
            based_on_icon: "👨‍💻",
            permission: "write",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expectMember(members[0]);
    await click(".o_knowledge_permission_panel_members > div:first-child .dropdown-toggle");
    await animationFrame();
    await click(".o-dropdown-item:contains('Can Read')");
    await animationFrame();
    // should show confirmation dialog as it will restrict user's access
    expect(".modal-title").toHaveText("Change Permission");
    await click(".modal-footer button:contains('Restrict Access')");
    await animationFrame();
    expectMember(members[0]);
    // article should now appear as desync
    expect("div:contains('Access Restricted') + button:contains('Restore')").toHaveCount(1);
    expect("div:contains('Access Restricted') > a").toHaveText("👨‍💻Workspace Article");
    expect.verifySteps(["change permission of member 1 to read on article 5", "reload record"]);
});

test.tags("desktop");
test("Upgrade inherited member permission", async () => {
    members = [
        {
            member_id: 1,
            name: "inherited",
            email: "inherited@example.com",
            based_on: true,
            based_on_name: "Parent Article",
            based_on_icon: "👨‍💻",
            permission: "read",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expectMember(members[0]);
    await click(".o_knowledge_permission_panel_members > div:first-child .dropdown-toggle");
    await animationFrame();
    await click(".o-dropdown-item:contains('Can Edit')");
    await animationFrame();
    // since we are modifying the perm from its parent we need to confirm
    expect(".modal").toHaveCount(1);
    await click(".modal-footer button:contains('Restrict Access')");
    await animationFrame();
    // member should not appear as "based on" anymore
    expectMember(members[0]);
    // article should not appear as desync
    expect("div:contains('Access Restricted') + button:contains('Restore')").toHaveCount(0);
    expect.verifySteps(["change permission of member 1 to write on article 5", "reload record"]);
});

test.tags("desktop");
test("Remove inherited member", async () => {
    members = [
        {
            member_id: 1,
            name: "inherited",
            email: "inherited@example.com",
            based_on: true,
            based_on_name: "Parent Article",
            based_on_icon: "👨‍💻",
            permission: "read",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expectMember(members[0]);
    await click(".o_knowledge_permission_panel_members .dropdown-toggle");
    await animationFrame();
    await click(".o_knowledge_permission_panel_remove_member");
    await animationFrame();
    // should show confirmation dialog as it will restrict user's access
    expect(".modal-title").toHaveText("Restrict Access");
    await click(".modal-footer button:contains('Restrict Access')");
    await animationFrame();
    expect(".o_knowledge_permission_panel_members > div").toHaveCount(0);
    // article should now appear as desync
    expect("div:contains('Access Restricted') + button:contains('Restore')").toHaveCount(1);
    expect("div:contains('Access Restricted') > a").toHaveText("👨‍💻Workspace Article");
    expect.verifySteps([`remove member 1 on article 5`, "reload record"]);
});

test.tags("desktop");
test("Can't remove an inherited member with permission = 'none'", async () => {
    members = [
        {
            member_id: 1,
            name: "inherited",
            email: "inherited@example.com",
            based_on: true,
            based_on_name: "Parent Article",
            based_on_icon: "👨‍💻",
            permission: "none",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expectMember(members[0]);
    expect(".o_select_menu_toggler_clear").toHaveCount(0);
});

test.tags("desktop");
test("Remove member while member has permission on a parent", async () => {
    members = [
        {
            member_id: 1,
            name: "member",
            email: "member@example.com",
            based_on: false,
            permission: "read",
        },
    ];
    await mountPermissionPanel(5, true);
    await animationFrame();
    expectMember(members[0]);
    await click(".o_knowledge_permission_panel_members .dropdown-toggle");
    await animationFrame();
    await click(".o_knowledge_permission_panel_remove_member");
    await animationFrame();
    // should not show modal
    expect(".modal-title").toHaveCount(0);
    // check that the inherited member is now shown
    expectMember({
        member_id: 1,
        name: "member",
        email: "member@example.com",
        based_on: true,
        based_on_name: "Workspace Article",
        based_on_icon: "👨‍💻",
        permission: "write",
    });
    expect.verifySteps(["remove member 1 on article 5", "reload record"]);
});

test.tags("desktop");
test("Change article while permission panel is open", async () => {
    await mountPermissionPanel(6, true);
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Can Read");
    await click(".fa-shield + div a:contains('👨‍💻Workspace Article')");
    await animationFrame();
    expect.verifySteps(["open 4"]);
    // check that panel has been reloaded
    expect(internalPermissionSelector).toHaveText("Can Edit");
});

test.tags("desktop");
test("Downgrade own permission", async () => {
    members = [
        {
            member_id: 1,
            name: "current",
            email: "current@example.com",
            permission: "write",
            partner_id: serverState.partnerId,
            partner_share: true,
        },
    ];
    patchWithCleanup(user, { isAdmin: false }); // not admin user
    mockService("action", {
        doAction: (action) => {
            if (action === "knowledge.ir_actions_server_knowledge_home_page") {
                expect.step("home");
            }
        },
    });
    await mountPermissionPanel(4, true);
    await animationFrame();
    expectMember(members[0]);
    await click(".o_knowledge_permission_panel_members > div:first-child .dropdown-toggle");
    await animationFrame();
    await click(".o-dropdown-item:contains('No Access')");
    await animationFrame();
    // should show confirmation dialog as it will restrict user's access
    expect(".modal-title").toHaveText("Leave Article");
    await click(".modal-footer button:contains('Lose Access')");
    await animationFrame();
    expect.verifySteps([
        "change permission of member 1 to none on article 4",
        "reload record",
        "home",
    ]);
});

test.tags("desktop");
test("Restore Article", async () => {
    members = [
        {
            member_id: 1,
            name: "internal",
            email: "internal@example.com",
            permission: "write",
        },
    ];
    await mountPermissionPanel(6, true);
    await animationFrame();
    expect(internalPermissionSelector).toHaveText("Can Read");
    // "based on" should not be visible
    expect(".knowledge_internal_permission_based_on_text").toHaveCount(0);
    // member's dropdown is disabled since its the only editor
    expectMember(members[0], true);
    // should show "restricted" message and "restore" button
    expect("div:contains('Access Restricted') + button:contains('Restore')").toHaveCount(1);
    expect("div:contains('Access Restricted') > a").toHaveText("👨‍💻Workspace Article");
    // update members list to check that restore will refetch members
    Object.assign(members[0], {
        based_on: 4,
        based_on_name: "Workspace Article",
        based_on_icon: "👨‍💻",
    });
    await click("button:contains('Restore')");
    await animationFrame();
    expect(".modal .btn-primary:contains('Restore Access')").toHaveCount(1);
    await click(".modal .btn-primary:contains('Restore Access')");
    await animationFrame();
    // check permission panel is updated and is now "based on"
    expect(internalPermissionSelector).toHaveText("Can Edit");
    expect(".knowledge_internal_permission_based_on_text").toHaveCount(1);
    expectMember(members[0]);
    // should not show "restricted" message and "restore" button anymore
    expect("div:contains('Access Restricted') + button:contains('Restore')").toHaveCount(0);
    expect.verifySteps(["restoring access on article 6", "reload record"]);
});
