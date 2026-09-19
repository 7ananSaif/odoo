import { PosConfig } from "@point_of_sale/../tests/unit/data/pos_config.data";

PosConfig._records = PosConfig._records.map((record) => ({
    ...record,
    iot_device_ids: [2, 3, 4, 5],
    iface_print_via_proxy: true,
    iface_printer_id: 2,
    iface_display_id: 3,
    iface_scale_id: 5,
}));
