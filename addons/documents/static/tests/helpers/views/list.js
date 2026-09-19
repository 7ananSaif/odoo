import { mountView } from "@web/../tests/web_test_helpers";
import { getEnrichedSearchArch } from "@documents/../tests/helpers/views/search";

export const basicDocumentsListArch = /* xml */ `
<list js_class="documents_list">
    <field name="type" width="25px" widget="documents_type_icon" nolabel="1"/>
    <field name="name"/>
    <field name="folder_id"/>
    <field name="owner_id"/>
    <field name="company_id" groups="base.group_multi_company"/>
    <field name="active"/>
    <field name="partner_id"/>
    <field name="id" invisible="1"/>
    <field name="available_embedded_actions_ids" widget="many2many_tags"/>
    <field name="access_token" invisible="1"/>
    <field name="mimetype" invisible="1"/>
    <field name="tag_ids" />
    <field name="alias_tag_ids"/>
    <field name="user_permission"/>
    <field name="display_name"/>
    <field name="attachment_id"/>
</list>
`;

export async function mountDocumentsListView(params = {}) {
    return mountView({
        actionMenus: {},
        type: "list",
        resModel: "documents.document",
        arch: basicDocumentsListArch,
        searchViewArch: getEnrichedSearchArch(),
        ...params,
    });
}
