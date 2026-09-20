export class KeypadModel {
    input = {
        value: "",
        selection: {
            start: 0,
            end: 0,
            direction: "none",
        },
        focus: false,
        /** @type {import("@mail/core/country_model").Country | null} */
        country: null,
    };
    showMore = false;

    constructor({ value = "" } = {}) {
        this.value = value;
    }

    reset() {
        Object.assign(this, new KeypadModel());
    }
}
