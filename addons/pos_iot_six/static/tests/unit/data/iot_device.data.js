import { IotDevice } from "@pos_iot/../tests/unit/data/iot_device.data";

IotDevice._records = [
    ...IotDevice._records,
    {
        id: 6,
        name: "IOT Payment Terminal SIX",
        iot_id: 2,
        iot_ip: "1.1.1.1",
        identifier: "payment_identifier",
        type: "payment",
        connection: "network",
        connected_status: "disconnected",
    },
];
