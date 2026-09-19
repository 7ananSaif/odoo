import { getFilledOrder } from "@point_of_sale/../tests/unit/utils";

export const getUrbanPiperFilledOrder = async (store) => {
    const order = await getFilledOrder(store);
    order.delivery_provider_id = store.models["pos.delivery.provider"].get(1);
    order.prep_time = 25.0;
    order.delivery_json = deliveryJson;
    order.setPartner(store.models["res.partner"].get(18));
    order.delivery_identifier = "OID001";
    return order;
};

export const deliveryJson = JSON.stringify({
    order: {
        details: {
            created: 1735879045123,
            delivery_datetime: 1735880545123,
            ext_platforms: [
                {
                    id: "TST-1756819673",
                    delivery_type: "partner",
                    name: "DoorDash",
                    extras: { order_otp: "123456" },
                },
            ],
        },
        store: { name: "Main Branch" },
        payment: [{ option: "card" }],
    },
});
