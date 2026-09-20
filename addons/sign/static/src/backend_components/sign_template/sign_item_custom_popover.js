import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useExternalListener, onWillStart, onMounted } from "@odoo/owl";

export class SignItemCustomPopover extends Component {
    static template = "sign.SignItemCustomPopover";
    static components = {};
    static props = {
        id: { type: Number },
        alignment: { type: String },
        header_title: {type: String },
        placeholder: { type: String },
        required: { type: Boolean },
        constant: { type: Boolean },
        option_ids: { type: Array },
        onValidate: { type: Function },
        type: { type: String },
        onDelete: { type: Function },
        onDuplicate: { type: Function },
        onClose: { type: Function },
        debug: { type: String },
        close: { type: Function },
        onCopyItem: { type: Function },
        num_options: {type: Number, optional: true},
        radio_set_id: {type: Number, optional: true},
    };

    setup() {
        this.alignmentOptions = [
            { title: _t("Left"), key: "left" },
            { title: _t("Center"), key: "center" },
            { title: _t("Right"), key: "right" },
        ];
        this.state = useState({
            alignment: this.props.alignment,
            placeholder: this.props.placeholder,
            constant: this.props.constant,
            required: this.props.required,
            option_ids: this.props.option_ids,
            num_options: this.props.num_options,
            radio_set_id: this.props.radio_set_id,
            selectionOptionsText: "",
        });
        this.orm = useService("orm");
        onWillStart(async() => {
            const options = await this.orm.searchRead(
                "sign.item.option",
                [["id", "in", this.props.option_ids]],
            );
            this.state.selectionOptionsText = options.map(option => option.value).join('\n');
        });

        /**
         * Focuses the selection options textarea when the popover is rendered
         */
        onMounted(() => {
            if (this.props.type === "selection") {
                const textarea = document.querySelector('.o_sign_selection_input_option textarea');
                if (textarea) {
                    textarea.focus();
                }
            }
        });

        this.notification = useService("notification");
        this.typesWithAlignment = new Set(["text", "textarea"]);
        useExternalListener(window, "keydown", this.onGlobalKeyDown, { capture: true });
    }

    onGlobalKeyDown(event) {
        if(event.key == 'c' && (event.ctrlKey || event.metaKey)) {
            this.notification.add(("Sign Item Copied"), {type: "success"});
            this.props.onCopyItem(this.props.id);
        } else if (event.key == 'Delete') {
            this.props.onDelete();
        }
    }

    handleNumOptionsChange(value) {
        if (Number(value) < 2) {
            return;
        }
        this.state['num_options'] = Number(value);
    }

    onChange(key, value) {
        this.state[key] = value;

        // Focuses the placeholder input if the item is set as read-only
        if (key === "constant") {
            if (value) {
                document.querySelector("#o_sign_name")?.focus();
            } else {
                this.state.placeholder = this.props.placeholder;
            }
        }
    }

    async onValidate() {
        if (this.props.type === "selection" && !this.state.selectionOptionsText) {
            this.notification.add(_t("Selection field cannot be empty. Please add at least one option."), {
                type: "warning",
            });
            return;
        }

        const options = this.state.selectionOptionsText.split('\n').map(opt => opt.trim()).filter(opt => opt);
        this.state.option_ids = await this.orm.call('sign.item.option', 'get_selection_ids_from_value', [null, options]);
        this.props.onValidate(this.state);
    }

    get showAlignment() {
        return this.typesWithAlignment.has(this.props.type);
    }

    onChangeSelectionOptions(value) {
        this.state.selectionOptionsText = value;
    }
}
