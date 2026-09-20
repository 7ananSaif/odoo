import { test, expect } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { Body } from "@l10n_it_pos/app/documents/fiscal_document/body/body";

definePosModels();

test("getLinesItDocument", async () => {
    const store = await setupPosEnv();
    store.addNewOrder();
    const order = store.getOrder();
    order.pricelist_id = false;
    order.currency_id = store.config.currency_id;
    const product = store.models["product.template"].get(11);
    product.taxes_id[0].amount = 0;
    product.taxes_id[0].tax_group_id.pos_receipt_label = "label";

    await store.addLineToOrder({ product_tmpl_id: product, qty: 2 }, order);
    expect(order.lines[0].price_unit).toBe(700);
    expect(order.totalDue).toBe(1400);

    const document = await mountWithCleanup(Body, {
        props: { order: order },
    });
    const document_lines = document.lines;

    expect(document_lines[0].unitPrice).toBe("700.00");

    expect(document.isFullDiscounted).toBe(false);
});
