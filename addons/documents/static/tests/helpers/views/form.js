export const basicDocumentsOperationFormArch = /* xml */ `
<form>
    <field name="display_name" invisible="1" force_save="1"/>
    <field name="user_permission" invisible="1" force_save="1"/>
    <field name="access_internal" invisible="1" force_save="1"/>
    <field name="access_via_link" invisible="1" force_save="1"/>
    <field name="document_ids" invisible="1"/>
    <field name="is_access_via_link_hidden" invisible="1" force_save="1"/>
    <field name="operation" readonly="1" invisible="1"/>
    <field name="attachment_id" invisible="1" force_save="1"/>
    <sheet>
        <field
            name="destination"
            widget="documents_user_folder_id_char"
            options="{
                'extraUpdateFields': [
                    'display_name', 'user_permission', 'access_internal', 'access_via_link',
                    'is_access_via_link_hidden',
                ],
                'ulClass': 'o_documents_operation_search_panel',
            }"
        />
    </sheet>
    <footer>
        <widget name="documents_operation_confirmation"/>
        <widget name="documents_operation_new_folder"/>
        <button string="Discard" special="cancel" class="btn-secondary"/>
    </footer>
</form>`;
