import { Component, useRef } from "@odoo/owl";

export class InputVerificationCode extends Component {
    static template = "hr_expense_stripe.InputVerificationCode";
    static props = {
        nbInputs: {
            type: Number,
        },
        onValidatedInput: {
            type: Function,
            optional: true,
        },
    };

    setup() {
        this.inputRefs = [];
        for (let i = 0; i < this.props.nbInputs; i++) {
            this.inputRefs.push(useRef(`input_${i}`));
        }
    }

    onFocus(ev) {
        const input_el = ev.target;
        input_el.setSelectionRange(0, input_el.value.length);
    }

    onInput(ev) {
        if (this.verificationCode.length === this.props.nbInputs && this.props.onValidatedInput) {
            this.props.onValidatedInput(this.verificationCode);
        }

        const i = this.getInputRefIndex(ev.target);
        if (i < this.props.nbInputs - 1 && ev.target.value.length === 1) {
            this.inputRefs[i + 1].el.focus();
        }
    }

    onPaste(ev) {
        if(!ev.clipboardData?.items) {
            return;
        }

        ev.preventDefault();

        let pastedData = ev.clipboardData.getData('text').split('');
        const start_index = this.getInputRefIndex(ev.target);
        for (const inputRef of this.inputRefs.slice(start_index)) {
            const inputEl = inputRef.el;
            inputEl.value = pastedData.shift() || "";
            this.onInput({ target: inputEl });
        }
    }

    onKeydown(ev) {
        const i = this.getInputRefIndex(ev.target);
        if (ev.key === 'Backspace' && ev.target.value === "" && i > 0) {
            ev.preventDefault();
            const newFocusedEl = this.inputRefs[i - 1].el;
            newFocusedEl.focus();
            newFocusedEl.value = "";
        } else if (ev.key === 'ArrowLeft') {
            ev.preventDefault();
            const indexToFocus = (i > 0) ? i - 1 : 0;
            this.inputRefs[indexToFocus].el.focus();
        } else if (ev.key === 'ArrowRight') {
            ev.preventDefault();
            const indexToFocus = (i < this.props.nbInputs - 1) ? i + 1 : i;
            this.inputRefs[indexToFocus].el.focus();
        }
    }

    get verificationCode() {
        let verificationCode = "";

        for (const input of this.inputRefs) {
            const value = input.el.value;
            if (value) {
                verificationCode += value;
            }
        }

        return verificationCode;
    }

    getInputRefIndex(el) {
        return this.inputRefs.findIndex(inputRef => inputRef.el == el);
    }

}
