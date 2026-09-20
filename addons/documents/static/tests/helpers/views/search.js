export function getEnrichedSearchArch(searchArch = "<search></search>") {
    const addons = `
        <separator/>
        <filter invisible="1" string="My Activities" name="filter_activities_my"
            domain="[('activity_user_id', '=', uid)]"/>
        <separator/>
        <filter invisible="1" string="Late Activities" name="activities_overdue"
            domain="[('my_activity_date_deadline', '&lt;', 'today')]"/>
        <filter invisible="1" string="Today Activities" name="activities_today"
            domain="[('my_activity_date_deadline', '=', 'today')]"/>
        <filter invisible="1" string="Future Activities" name="activities_upcoming_all"
            domain="[('my_activity_date_deadline', '&gt;', 'today')]"/>
        <searchpanel class="o_documents_search_panel">
            <field name="user_folder_id" string="Folders"/>
        </searchpanel>
    `;

    return searchArch.split("</search>")[0] + addons + "</search>";
}
