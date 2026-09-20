import {
    getService,
    makeMockEnv,
    patchWithCleanup,
    MockServer,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { registry } from "@web/core/registry";
import { uuidv4 } from "@point_of_sale/utils";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { unpatchPrepDataService } from "@pos_enterprise/app/services/data_service";
import { unpatchDataServiceOptions } from "@pos_enterprise/app/models/data_service_options";

export const setupPosEnvForPrepDisplay = async () => {
    unpatchPrepDataService();
    unpatchDataServiceOptions();
    registry.category("services").remove("preparation_display");
    return await setupPosEnv();
};

export const setupPosPrepDisplayEnv = async () => {
    // Do not change these variables, they are in accordance with the setup data
    odoo.access_token = uuidv4();
    odoo.info = {
        isEnterprise: true,
    };
    odoo.preparation_display = {
        id: 1,
        name: "Test Kitchen Display",
        access_token: uuidv4(),
    };
    patchWithCleanup(session, {
        db: "test",
        data: {
            config_id: 1,
        },
    });

    // Removing `pos` and its dependent services to avoid conflicts during `preparation_display` data loading.
    // Both `pos` and `preparation_display` rely on `pos_data`, but some models required by `preparation_display` (e.g., `prep.prep.order`)
    // are missing when `pos` is loaded. Hence, these services are excluded.
    const serviceNames = ["contextual_utils_service", "debug", "report", "pos"];
    serviceNames.forEach((serviceName) => registry.category("services").remove(serviceName));

    await makeMockEnv();
    const store = getService("preparation_display");
    await mountWithCleanup(PrepDisplay);
    return store;
};

/**
 * Generate multiple lines at once.
 * You can either pass specific line configs or use defaults.
 */
export const generateLinesData = (lines = []) => {
    if (!lines.length) {
        return [
            generateLine({
                qty: 3,
                price_unit: 3,
                product_id: 5,
                full_product_name: "TEST",
                tax_ids: [1],
            }),
            generateLine({
                qty: 2,
                price_unit: 3,
                product_id: 6,
                full_product_name: "TEST 2",
                tax_ids: [2],
            }),
        ];
    }
    return lines.map((line) => generateLine(line));
};

/**
 * Generate a single order line object in standard Odoo POS format.
 */
export const generateLine = ({
    qty = 1,
    price_unit = 1,
    product_id = 1,
    full_product_name = "Default Product",
    uuid = uuidv4(),
    tax_ids = [],
    price_type = "original",
    attribute_value_ids = [],
    extraLineFields = {},
}) => [
    0,
    0,
    {
        qty,
        attribute_value_ids,
        price_unit,
        uuid,
        price_subtotal: qty * price_unit,
        price_subtotal_incl: qty * price_unit,
        price_type,
        product_id,
        tax_ids,
        full_product_name,
        write_date: "2019-03-11 09:30:06",
        ...extraLineFields,
    },
];

/**
 * Generate order data with customizable fields and dynamic lines.
 */
export const generateOrderData = ({ extraOrderFields = {}, lines = [] }) => [
    {
        create_date: "2019-03-11 09:30:06",
        write_date: "2019-03-11 09:30:06",
        access_token: uuidv4(),
        name: "Order 00001",
        date_order: "2019-03-11 09:30:06",
        user_id: 2,
        company_id: 1,
        pricelist_id: 1,
        sequence_number: 1,
        session_id: 1,
        config_id: 1,
        state: "draft",
        ticket_code: "4kqm5",
        tracking_number: "0001",
        uuid: uuidv4(),
        lines: generateLinesData(lines),
        ...extraOrderFields,
    },
];

export const createPrepDisplayTicket = async (store, orderData = {}) => {
    const data = generateOrderData(orderData);
    MockServer.env["pos.order"].sync_from_ui(data);
    await store.data.initData();
};

export const createComboPrepDisplayTicket = async (store) => {
    await createPrepDisplayTicket(store, {
        lines: [
            {
                qty: 1,
                price_unit: 0,
                product_id: 7,
                full_product_name: "Product combo",
                tax_ids: [2],
                uuid: "39335cf8-acee-4275-8985-38dfa4b78a16",
            },
            {
                qty: 1,
                price_unit: 1,
                product_id: 8,
                full_product_name: "Wood chair",
                tax_ids: [2],
                combo_item_id: 1,
                uuid: "cf9c105b-df50-4c1e-b8df-a965b231f9f2",
            },
            {
                qty: 1,
                price_unit: 2,
                product_id: 10,
                full_product_name: "Wood desk",
                tax_ids: [2],
                combo_item_id: 3,
                uuid: "56780df0-c429-4dc8-a838-4c64fe2e40be",
            },
        ],
        extraOrderFields: {
            relations_uuid_mapping: {
                "pos.order.line": {
                    "cf9c105b-df50-4c1e-b8df-a965b231f9f2": {
                        combo_parent_id: "39335cf8-acee-4275-8985-38dfa4b78a16",
                    },
                    "56780df0-c429-4dc8-a838-4c64fe2e40be": {
                        combo_parent_id: "39335cf8-acee-4275-8985-38dfa4b78a16",
                    },
                },
            },
        },
    });
};
