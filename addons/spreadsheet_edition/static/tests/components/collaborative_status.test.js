import { describe, expect, test } from "@odoo/hoot";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { contains, makeMockEnv, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Model, stores, LocalTransportService } from "@odoo/o-spreadsheet";

import { CollaborativeStatus } from "@spreadsheet_edition/bundle/components/collaborative_status/collaborative_status";
import { Component, onMounted, onWillUnmount, xml } from "@odoo/owl";
const { useStoreProvider, ModelStore, ClientFocusStore } = stores;

describe.current.tags("desktop");
defineSpreadsheetModels();

class Parent extends Component {
    static template = xml`<CollaborativeStatus/>`;
    static components = { CollaborativeStatus };
    static props = {
        model: Object,
    };

    setup() {
        const stores = useStoreProvider();
        stores.inject(ModelStore, this.props.model);

        onMounted(() => {
            this.props.model.on("update", this, () => this.render(true));
            stores.on("store-updated", this, this.render.bind(this, true));
        });
        onWillUnmount(() => {
            this.props.model.off("update", this);
            stores.off("store-updated", this);
        });
    }
}

const CLIENTS = {
    alice: {
        id: "alice",
        name: "Alice",
        position: { sheetId: "AliceSheet", col: 5, row: 5 },
        userId: 1,
    },
    bob: { id: "bob", name: "Bob", position: { sheetId: "BobSheet", col: 20, row: 20 }, userId: 2 },
    fromId(id) {
        return { id, name: id, position: { sheetId: "AliceSheet", col: 2, row: 2 }, userId: id };
    },
};

async function mountCollaborativeStatusComponent(clients = []) {
    const transportService = new LocalTransportService();
    const model = new Model({}, { transportService });
    const env = await makeMockEnv({ model });

    for (const client of clients) {
        transportService.sendMessage({
            type: "CLIENT_JOINED",
            version: 1,
            client,
        });
    }

    const parent = await mountWithCleanup(Parent, { env, props: { model: env.model } });
    return { env, model, transportService, parent };
}

test("Show user bubble with less than 10 users", async function () {
    await mountCollaborativeStatusComponent([CLIENTS.alice, CLIENTS.bob]);
    expect(".o_spreadsheet_user").toHaveCount(2);
});

test("Show user bubble with more than 10 users", async function () {
    const clients = [CLIENTS.alice, CLIENTS.bob].concat(
        Array(10)
            .keys()
            .map((x) => CLIENTS.fromId(3 + x))
            .toArray()
    );
    await mountCollaborativeStatusComponent(clients);

    expect(".o_spreadsheet_user .justify-content-between").toHaveCount(10);
    expect(".o_spreadsheet_more_users").toHaveText("+2");

    await contains(".o_spreadsheet_more_users").hover();
    expect(".o_spreadsheet_user").toHaveCount(12);
});

test("Jump to user", async function () {
    const { parent } = await mountCollaborativeStatusComponent([CLIENTS.alice, CLIENTS.bob]);
    const clientFocusStore = parent.env.getStore(ClientFocusStore);

    const funSpy = [];
    clientFocusStore.jumpToClient = (clientId) => {
        funSpy.push(clientId);
    };

    await contains(".o_spreadsheet_users div:nth-child(1) img").click();

    expect(funSpy).toInclude("alice");
});

test("Show client tags on hover", async function () {
    const { parent } = await mountCollaborativeStatusComponent([CLIENTS.alice, CLIENTS.bob]);
    const clientFocusStore = parent.env.getStore(ClientFocusStore);

    await contains(".o_spreadsheet_users div:nth-child(1) img").hover();

    expect(clientFocusStore.focusedClients).toInclude("alice");
});
