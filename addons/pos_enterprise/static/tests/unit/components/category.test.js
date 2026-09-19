import { test, expect } from "@odoo/hoot";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Category } from "@pos_enterprise/app/components/category/category";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

definePosPrepDisplayModels();

test("shouldShowCategory", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    const comp = await mountWithCleanup(Category, { props: { category: category } });
    const result = comp.shouldShowCategory;
    expect(result).toBe(1);
    expect(comp.products.length).toBe(1);
});

test("preparation_display_service.toggleCategory", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    await mountWithCleanup(Category, { props: { category: category } });
    // select category
    store.toggleCategory(category);
    expect(store.selectedCategoryIds.has(category.id)).toBe(true);
    expect(store.selectedProductIds.size).toBe(0);
    // unselect category
    store.toggleCategory(category);
    expect(store.selectedCategoryIds.has(category.id)).toBe(false);
});

test("preparation_display_service.toggleProduct", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);
    const category = store.data.models["pos.category"].getAll()[0];
    const comp = await mountWithCleanup(Category, { props: { category: category } });
    const product = comp.products[0];
    // select product
    store.toggleProduct(product);
    expect(store.selectedProductIds.has(product.id)).toBe(true);
    expect(store.selectedCategoryIds.size).toBe(0);
    // unselect product
    store.toggleProduct(product);
    expect(store.selectedProductIds.has(product.id)).toBe(false);
});
