import { describe, expect, test } from "@odoo/hoot";
import { defineSpreadsheetModels, Partner } from "@spreadsheet/../tests/helpers/data";
import { makeStore } from "@spreadsheet/../tests/helpers/stores";
import { onRpc, fields } from "@web/../tests/web_test_helpers";

import { GlobalFilterSuggestionsStore } from "@spreadsheet_edition/bundle/global_filters/global_filter_suggestions/global_filter_suggestions_store";

import { insertListInSpreadsheet } from "@spreadsheet/../tests/helpers/list";

describe.current.tags("headless");

defineSpreadsheetModels();

test("suggestions from a single data source", async () => {
    onRpc("get_search_view_archs", ({ args }) => {
        expect(args).toEqual([["action_partner"]]);
        return {
            partner: [
                /*xml*/ `
                <search>
                    <field name="product_id" string="My product filter"/>
                    <field name="tag_ids"/>
                    <!-- ignore non relational fields -->
                    <field name="name"/>
                    <field name="create_date"/>
                </search>
                `,
            ],
        };
    });
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([
        {
            modelName: "product",
            modelDisplayName: "Product",
            label: "My product filter",
            fieldMatching: {
                partner: {
                    chain: "product_id",
                    type: "many2one",
                },
            },
        },
        {
            modelName: "tag",
            label: "Tags",
            modelDisplayName: "Tag",
            fieldMatching: {
                partner: {
                    chain: "tag_ids",
                    type: "many2many",
                },
            },
        },
    ]);
});

test("suggestions for different models", async () => {
    onRpc("get_search_view_archs", ({ args }) => {
        expect(args).toEqual([["action_partner", "action_product"]]);
        return {
            partner: [
                /*xml*/ `
                <search>
                    <field name="product_id"/>
                    <!-- only currency_id is matching both -->
                    <field name="currency_id"/>
                </search>
                `,
            ],
            product: [
                /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
            ],
        };
    });
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    insertListInSpreadsheet(model, {
        model: "product",
        columns: [],
        actionXmlId: "action_product",
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([
        {
            modelName: "res.currency",
            modelDisplayName: "Currency",
            label: "Currency",
            fieldMatching: {
                partner: {
                    chain: "currency_id",
                    type: "many2one",
                },
                product: {
                    chain: "currency_id",
                    type: "many2one",
                },
            },
        },
    ]);
});

test("Filter with no matching is not proposed", async () => {
    onRpc("get_search_view_archs", ({ args }) => {
        expect(args).toEqual([["action_partner"]]);
        return {
            partner: [
                /*xml*/ `
                <search>
                    <field name="product_id"/>
                </search>
                `,
            ],
        };
    });
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    insertListInSpreadsheet(model, {
        model: "res.country",
        columns: [],
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([]);
});

test("suggestions if field is duplicated in different archs", async () => {
    onRpc("get_search_view_archs", ({ args }) => ({
        partner: [
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
        ],
        product: [
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
        ],
    }));
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    insertListInSpreadsheet(model, {
        model: "product",
        columns: [],
        actionXmlId: "action_product",
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([
        {
            modelName: "res.currency",
            modelDisplayName: "Currency",
            label: "Currency",
            fieldMatching: {
                partner: {
                    chain: "currency_id",
                    type: "many2one",
                },
                product: {
                    chain: "currency_id",
                    type: "many2one",
                },
            },
        },
    ]);
});

test("don't suggest if multiple matches are possible with the same arch", async () => {
    Partner._fields.other_currency_id = fields.Many2one({
        relation: "res.currency",
        string: "Currency2",
        searchable: true,
    });
    onRpc("get_search_view_archs", ({ args }) => ({
        partner: [
            /*xml*/ `
                <search>
                    <!-- Two currencies -->
                    <field name="other_currency_id"/>
                    <field name="currency_id"/>
                </search>
                `,
        ],
        product: [
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
        ],
    }));
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    insertListInSpreadsheet(model, {
        model: "product",
        columns: [],
        actionXmlId: "action_product",
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([]);
});

test("don't suggest if multiple matches are possible with different archs", async () => {
    Partner._fields.other_currency_id = fields.Many2one({
        relation: "res.currency",
        string: "Currency2",
        searchable: true,
    });
    onRpc("get_search_view_archs", ({ args }) => ({
        partner: [
            /*xml*/ `
                <search>
                    <field name="other_currency_id"/>
                </search>
                `,
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
        ],
        product: [
            /*xml*/ `
                <search>
                    <field name="currency_id"/>
                </search>
                `,
        ],
    }));
    const { store, model } = await makeStore(GlobalFilterSuggestionsStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [],
        actionXmlId: "action_partner",
    });
    insertListInSpreadsheet(model, {
        model: "product",
        columns: [],
        actionXmlId: "action_product",
    });
    const suggestions = await store.suggestionsPromise;
    expect(suggestions).toEqual([]);
});
