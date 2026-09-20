import { mailModels } from "@mail/../tests/mail_test_helpers";
import {
    defineActions,
    defineMenus,
    defineModels,
    fields,
    models,
} from "@web/../tests/web_test_helpers";
import { handleDefaultStudioRoutes } from "./view_editor_tests_utils";

export function defineStudioEnvironment() {
    class IrMenu extends models.Model {
        _name = "ir.ui.menu";

        name = fields.Char();

        _records = [
            {
                id: 1,
                name: "Partner 1",
            },
            {
                id: 11,
                name: "Partner 11",
            },
            {
                id: 12,
                name: "Partner 12",
            },
        ];

        _views = {
            form: `
                <form>
                    <field name="name"/>
                </form>`,
        };
    }

    class Partner extends models.Model {
        _name = "partner";

        name = fields.Char();
        date = fields.Date();
        pony_id = fields.Many2one({ relation: "pony" });
        dog_id = fields.Many2one({ relation: "dog" });
        unit_amount = fields.Float({
            string: "Unit Amount",
            aggregator: "sum",
        });

        _records = [
            {
                name: "Yop",
                date: "2024-12-12",
                pony_id: 1,
                unit_amount: 2,
            },
        ];

        _views = {
            form: `
                <form>
                    <field name="name"/>
                    <field name="date"/>
                    <field name="pony_id"/>
                </form>`,

            "kanban,1": `
                <kanban>
                    <field name="name"/>
                    <field name="date"/>
                    <field name="pony_id"/>
                    <templates>
                        <t t-name="card">
                            <div>
                                <field name="name"/>
                            </div>
                        </t>
                    </templates>
                </kanban>`,

            "list,2": `
                <list>
                    <field name="name"/>
                </list>`,

            grid: `
                <grid>
                    <field name="pony_id" type="row"/>
                    <field name="unit_amount" type="measure"/>
                    <field name="date" type="col">
                        <range name="week" string="Week" span="week" step="day"/>
                    </field>
                    <field name="unit_amount" type="measure" widget="float_time"/>
                </grid>`,

            pivot: `<pivot/>`,

            search: `
                <search>
                    <field name="name"/>
                    <field name="date"/>
                </search>`,
        };
    }

    class Pony extends models.Model {
        _name = "pony";

        name = fields.Char();
        partner_ids = fields.One2many({ relation: "partner" });
        size = fields.Selection({
            selection: [["little", "Little"]],
        });

        _records = [
            { name: "Rainbow Dash", size: "little" },
            { name: "Applejack", size: "little" },
        ];

        _views = {
            form: `
                <form>
                    <field name="name"/>
                    <field name="size"/>
                    <field name='partner_ids'>
                        <form>
                            <sheet>
                                <field name='display_name'/>
                            </sheet>
                        </form>
                    </field>
                </form>`,

            search: `
                <search>
                    <filter name="apple" string="apple" domain="[('name', 'ilike', 'Apple')]" />
                </search>`,

            list: `
                <list>
                    <field name="name"/>
                </list>`,
        };
    }

    class Dog extends models.Model {
        _name = "dog";

        name = fields.Char();
        partner_ids = fields.One2many({ relation: "partner" });

        _views = {
            form: `
                <form>
                    <field name="name"/>
                    <field name='partner_ids'>
                        <form>
                            <sheet>
                                <field name='display_name'/>
                            </sheet>
                        </form>
                    </field>
                </form>`,

            search: `
                <search>
                    <field name="name"/>
                </search>`,

            list: `
                <list sample="1">
                    <field name="name"/>
                    <field name="partner_ids" optional="hide"/>
                </list>`,

            kanban: `
                <kanban sample="1">
                    <field name="name"/>
                    <templates>
                        <t t-name="card">
                            <div>
                                <field name="name"/>
                            </div>
                        </t>
                    </templates>
                </kanban>`,
        };
    }

    class Settings extends models.Model {
        _name = "settings";

        _views = {
            list: `
                <list sample="1">
                    <field name="display_name"/>
                </list>`,
        };
    }

    class BaseAutomation extends models.Model {
        _name = "base.automation";

        name = fields.Char();

        _views = {
            list: `
                <list>
                    <field name="name"/>
                </list>`,
            form: `
                <form>
                    <field name="name"/>
                </form>`,
            kanban: `
                <kanban>
                    <field name="name"/>
                    <templates>
                        <t t-name="card">
                            <div>
                                <field name="name"/>
                            </div>
                        </t>
                    </templates>
                </kanban>`,
        };
    }

    defineModels({ ...mailModels, Pony, Partner, Dog, Settings, BaseAutomation, IrMenu });

    defineActions([
        {
            id: 1,
            name: "partner Action",
            res_model: "partner",
            type: "ir.actions.act_window",
            xml_id: "partner_action_1",
            view_mode: "kanban",
            views: [
                [1, "kanban"],
                [2, "list"],
                [false, "grid"],
                [false, "pivot"],
                [false, "form"],
                [false, "search"],
            ],
            group_ids: [],
        },
        {
            id: 11,
            name: "partner Action (list first)",
            res_model: "partner",
            type: "ir.actions.act_window",
            xml_id: "partner_action_11",
            views: [
                [2, "list"],
                [1, "kanban"],
                [false, "grid"],
                [false, "search"],
                [false, "form"],
            ],
            group_ids: [],
            context: {
                active_id: 1,
            },
        },
        {
            id: 2,
            name: "Pony Action",
            res_model: "pony",
            type: "ir.actions.act_window",
            xml_id: "pony_action_1",
            context: "{'default_name': 'foo'}",
            views: [
                [false, "list"],
                [false, "search"],
                [false, "form"],
            ],
            group_ids: [],
        },
        {
            id: 3,
            name: "Dog Action",
            res_model: "dog",
            type: "ir.actions.act_window",
            xml_id: "dog_action_1",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "search"],
                [false, "form"],
            ],
            group_ids: [],
        },
        {
            id: 4,
            name: "Settings",
            res_model: "settings",
            type: "ir.actions.act_window",
            xml_id: "settings_action_1",
            views: [
                [false, "list"],
                [false, "search"],
            ],
            group_ids: [],
        },
    ]);

    defineMenus(
        [
            {
                id: 1,
                children: [
                    {
                        id: 11,
                        name: "Partners 11",
                        appID: 1,
                        actionID: 1,
                        xmlid: "menu_11",
                    },
                    {
                        id: 12,
                        name: "Partners 12",
                        appID: 1,
                        actionID: 11,
                        xmlid: "menu_12",
                    },
                ],
                name: "Partners 1",
                appID: 1,
                actionID: 1,
                xmlid: "app_1",
            },
            {
                id: 2,
                name: "Ponies",
                appID: 2,
                actionID: 2,
                xmlid: "app_2",
                webIcon: "fa fa-diamond,#FFFFFF,#C6572A",
            },
            {
                id: 3,
                name: "Dogs",
                appID: 3,
                actionID: 3,
                xmlid: "app_3",
            },
            {
                id: 4,
                name: "Settings",
                appID: 4,
                actionID: 4,
                xmlid: "app_4",
            },
        ],
        { mode: "replace" }
    );

    handleDefaultStudioRoutes();
}
