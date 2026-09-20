import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("databases_tour", {
    url: "/odoo",
    steps: () => [
        {
            content: 'open databases app',
            trigger: '.o_app[data-menu-xmlid="databases.menu_main_databases"]',
            run: 'click',
        },
        {
            content: 'open the New dropdown',
            trigger: '.o_list_button_add',
            run: 'click',
        },
        {
            content: 'add a new database',
            trigger: '.o-dropdown-item:contains("New Project")',
            run: 'click',
        },
        {
            content: 'give the database a name',
            trigger: '.o_field_widget[name="name"] textarea',
            run: 'edit Fidu Client',
        },
        {
            content: 'open the database tab',
            trigger: 'a[role="tab"][name="database"]',
            run: 'click',
        },
        {
            content: 'open the hosting type dropdown',
            trigger: '.o_field_widget[name="database_hosting"] input',
            run: 'click',
        },
        {
            content: 'set the SaaS hosting type',
            trigger: '.o_select_menu_item:contains("On Premise")',
            run: 'click',
        },
        {
            content: 'set the database URL',
            trigger: '.o_field_widget[name="database_url"] input',
            run: 'edit http://my.database.tld',
        },
        {
            content: 'set the database name',
            trigger: '.o_field_widget[name="database_name"] input',
            run: 'edit my-database',
        },
        {
            content: 'set the database API login',
            trigger: '.o_field_widget[name="database_api_login"] input',
            run: 'edit admin@database.tld',
        },
        {
            content: 'set the database API key',
            trigger: '.o_field_widget[name="database_api_key"] input',
            run: 'edit myApiKey',
        },
        {
            content: 'check Fetch Documents',
            trigger: '.o_field_widget.o_field_boolean[name="database_fetch_documents"]:has(~span:contains(Documents)) input',
            run: 'check',
        },
        {
            content: 'check Fetch Journal entries: Draft',
            trigger: '.o_field_widget.o_field_boolean[name="database_fetch_draft_entries"]:has(~span:contains(Draft Journal Entries)) input',
            run: 'check',
        },
        {
            content: 'check Fetch Tax Returns',
            trigger: '.o_field_widget.o_field_boolean[name="database_fetch_tax_returns"]:has(~span:contains(Tax Returns)) input',
            run: 'check',
        },
        {
            content: 'auto-save the database by going back to the list',
            trigger: 'ol.breadcrumb a[href="/odoo/databases"]',
            run: 'click',
        },
        {
            content: 'click on the database row',
            trigger: '.o_data_cell:contains("Fidu Client")',
            run: 'click',
        },
        {
            content: 'should have opened the list of tasks',
            trigger: '.o_kanban_project_tasks',
        },
        {
            content: 'go back to the list',
            trigger: 'ol.breadcrumb a[href="/odoo/databases"]',
            run: 'click',
        },
        {
            content: 'open the database settings again',
            trigger: 'tr:has(.o_data_cell:contains("Fidu Client")) button[name="action_open_self"]',
            run: 'click',
        },
        {
            content: 'there is the database tab (back on the project settings)',
            trigger: 'a[role="tab"][name="database"]',
        },
        {
            content: 'open the New dropdown',
            trigger: '.o_form_button_create',
            run: 'click',
        },
        {
            content: 'add a new database from the template',
            trigger: '.o-dropdown-item:contains("Database Template")',
            run: 'click',
        },
        {
            content: 'give the database a name',
            trigger: '.modal-body .o_field_widget[name="name"] input',
            run: 'edit Other Client',
        },
        {
            content: 'open the hosting type dropdown',
            trigger: '.modal-body .o_field_widget[name="database_hosting"] input',
            run: 'click',
        },
        {
            content: 'set the SaaS hosting type',
            trigger: '.o_select_menu_item:contains("On Premise")',
            run: 'click',
        },
        {
            content: 'set the database URL',
            trigger: '.modal-body .o_field_widget[name="database_url"] input',
            run: 'edit http://other.database.tld',
        },
        {
            content: 'set the database name',
            trigger: '.modal-body .o_field_widget[name="database_name"] input',
            run: 'edit other-database',
        },
        {
            content: 'set the database API login',
            trigger: '.modal-body .o_field_widget[name="database_api_login"] input',
            run: 'edit admin@database.tld',
        },
        {
            content: 'set the database API key',
            trigger: '.modal-body .o_field_widget[name="database_api_key"] input',
            run: 'edit myApiKey',
        },
        {
            content: 'create the project',
            trigger: '.modal-footer button[name="create_project_from_template"]',
            run: 'click',
        },
        {
            content: 'go back to the list',
            trigger: 'ol.breadcrumb a[href="/odoo/databases"]',
            run: 'click',
        },
        {
            content: 'open the settings of the database created from the template',
            trigger: 'tr:has(.o_data_cell:contains("Other Client")) button[name="action_open_self"]',
            run: 'click',
        },
        {
            content: 'open the database tab',
            trigger: 'a[role="tab"][name="database"]',
            run: 'click',
        },
    ],
});
