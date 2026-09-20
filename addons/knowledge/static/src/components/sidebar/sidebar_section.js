import { KnowledgeSidebarRow } from "./sidebar_row";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useChildSubEnv, useState } from "@odoo/owl";

/**
 * This file defines the different sections used in the sidebar.
 * Each section is responsible of displaying an array of root articles and
 * their children.
 */

export class KnowledgeSidebarSection extends Component {
    static template = "";
    static props = {
        rootIds: Array,
        unfoldedIds: Set,
        record: Object,
    };
    static components = {
        KnowledgeSidebarRow,
    };

    setup() {
        super.setup();
        const foldedSections = JSON.parse(browser.localStorage.getItem("knowledge.folded.sections") ?? "{}");
        this.state = useState({
            isFolded: foldedSections[this.getSectionIdentifier()] || this.props.rootIds.length === 0,
        });

        // Unfold the section of the current article:
        useRecordObserver((record) => {
            if (record.data.category === this.getSectionIdentifier()) {
                this.state.isFolded = false;
            }
        });

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup('base.group_user');
            this.canCreateArticle = await user.checkAccessRight('knowledge.article', 'create');
        });
    }

    toggleSidebarSection() {
        this.state.isFolded = !this.state.isFolded;
        // Persist the new folding state in local storage:
        const foldedSections = JSON.parse(browser.localStorage.getItem("knowledge.folded.sections") ?? "{}");
        foldedSections[this.getSectionIdentifier()] = this.state.isFolded;
        browser.localStorage.setItem("knowledge.folded.sections", JSON.stringify(foldedSections));
    }
}

export class KnowledgeSidebarFavoriteSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarFavoriteSection";

    setup() {
        super.setup();

        // (Un)fold in the favorite tree by default.
        useChildSubEnv({
            fold: id => this.env.fold(id, true),
            unfold: id => this.env.unfold(id, true),
        });
    }

    getSectionIdentifier() {
        return "favorites";
    }
}

export class KnowledgeSidebarWorkspaceSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarWorkspaceSection";

    setup() {
        super.setup();
        this.command = useService("command");
    }

    createRoot() {
        this.env.createArticle("workspace");
    }

    searchHiddenArticle() {
        this.command.openMainPalette({searchValue: "$"});
    }

    getSectionIdentifier() {
        return "workspace";
    }
}

export class KnowledgeSidebarSharedSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarSharedSection";

    getSectionIdentifier() {
        return "shared";
    }
}

export class KnowledgeSidebarPrivateSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarPrivateSection";

    createRoot() {
        this.env.createArticle("private");
    }

    getSectionIdentifier() {
        return "private";
    }
}
