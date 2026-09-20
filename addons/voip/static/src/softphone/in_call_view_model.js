import { KeypadModel } from "@voip/softphone/keypad_model";

export class InCallViewModel {
    activeView = "default";
    keypad = {
        isOpen: false,
        state: new KeypadModel(),
    };
    transferView = {
        /* possible values: contacts, keypad */
        activeView: "contacts",
        keypad: new KeypadModel(),
    };

    reset() {
        Object.assign(this, new InCallViewModel());
    }
}
