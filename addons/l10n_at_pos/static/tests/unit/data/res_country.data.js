import { ResCountry } from "@point_of_sale/../tests/unit/data/res_country.data";

ResCountry._records = [
    ...ResCountry._records,
    {
        id: 12,
        name: "Austria",
        code: "AT",
        vat_label: "USt",
    },
];
