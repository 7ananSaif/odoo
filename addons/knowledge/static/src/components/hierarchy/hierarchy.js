import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { KnowledgeFormStatusIndicator } from "@knowledge/components/form_status_indicator/form_status_indicator";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";

import KnowledgeIcon from "@knowledge/components/knowledge_icon/knowledge_icon";

import { Component, useState } from "@odoo/owl";

export default class KnowledgeHierarchy extends Component {
    static components = {
        Dropdown,
        DropdownItem,
        KnowledgeIcon,
        KnowledgeFormStatusIndicator,
    };
    static props = { record: Object };
    static template = "knowledge.KnowledgeHierarchy";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({
            articleName: this.props.record.data.name,
            isLoadingArticleHierarchy: false,
        });
        useRecordObserver((record) => {
            if (this.state.articleName !== record.data.name) {
                this.state.articleName = record.data.name;
            }
        });
    }

    /**
     * Whether to display the dropdown toggle used to get the articles that are between the root
     * and the parent article. It is only shown if there are any articles to show (parent_path is
     * of the form "1/2/3/4/", hence length > 4 as condition)
     */
    get displayDropdownToggle() {
        return this.props.record.data.parent_path.split("/").length > 4;
    }

    get isReadonly() {
        return this.props.record.data.is_locked || !this.props.record.data.user_can_write;
    }

    get parentId() {
        return this.props.record.data.parent_id?.id;
    }

    get parentName() {
        return this.props.record.data.parent_id?.display_name;
    }

    get rootId() {
        return this.props.record.data.root_article_id.id;
    }

    get rootName() {
        return this.props.record.data.root_article_id.display_name;
    }

    /**
     * Load the articles that should be shown in the dropdown
     */
    async loadHierarchy() {
        this.articleHierarchy = await this.orm.call(
            "knowledge.article",
            "get_article_hierarchy",
            [this.props.record.resId],
            { exclude_article_ids: [this.rootId, this.parentId, this.props.record.resId] },
        );
        this.state.isLoadingArticleHierarchy = false;
    }

    /**
     * If needed, will show the loading indicator in the dropdown and start the loading
     * of the articles to show in it
     */
    async onBeforeOpen() {
        this.state.isLoadingArticleHierarchy = true;
        this.loadHierarchy();
    }
}
