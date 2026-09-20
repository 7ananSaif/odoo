import { Component, onWillUpdateProps, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { fileTypeMagicWordMap } from "@web/views/fields/image/image_field";

export class SignTemplateSidebarRoleItems extends Component {
    static template = "sign.SignTemplateSidebarRoleItems";
    static components = {
        RecordSelector,
        Dropdown,
        DropdownItem,
    };
    static props = {
        signItemTypes: { type: Array },
        id: { type: Number },
        name: { type: String },
        signTemplateId: { type: Number },
        isSignRequest: { type: Boolean },
        updateRoleName: { type: Function },
        roleId: { type: Number, optional: true },
        colorId: { type: Number },
        isInputFocused: { type: Boolean, optional: true },
        isCollapsed: { type: Boolean },
        updateCollapse: { type: Function },
        onDelete: { type: Function },
        itemsCount: { type: Number },
        hasSignRequests: { type: Boolean },
        onFieldNameInputKeyUp: { type: Function },
        assignTo: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.roleInputRef = useRef('role_input');
        const profilePic = this.getImageSrc(this.props.assignTo);
        this.state = useState({
            roleName: this.props.name,
            canEditSignerName: false,
            profilePic: profilePic || "",
        });
        this.icon_type = {
            signature: "fa-pencil-square-o",
            initial: "fa-pencil-square-o",
            stamp: "fa-pencil-square-o",
            text: "fa-font",
            textarea: "fa-bars",
            checkbox: "fa-check-square-o",
            radio: "fa-dot-circle-o",
            selection: "fa-angle-down",
            strikethrough: "fa-strikethrough",
        };
        onWillUpdateProps((nextProps) => {
            if (nextProps.name !== this.state.roleName) {
                this.state.roleName = nextProps.name;
            }
        })
    }

    async onDeleteDialog() {
        const hasItems = this.props.itemsCount > 0;
        if (!hasItems) {
            this.props.onDelete();
        } else {
            this.dialog.add(ConfirmationDialog, {
                title: _t('Delete signer "%s"', this.state.roleName),
                body: _t("Do you really want to delete this signer?"),
                confirmLabel: _t("Delete"),
                confirm: () => {
                    this.props.onDelete();
                },
                cancel: () => {},
            });
        }
    }

    onSignerNameTextClick() {
        /* If the input is not focused, focus it. */
        if (!this.props.hasSignRequests && !this.props.isCollapsed) {
            this.state.canEditSignerName = true;
            const input = this.roleInputRef.el;

            const waitForVisibility = () => {
                if (input && !input.parentElement.parentElement.classList.contains('d-none')) {
                    // Input is visible, so we can focus
                    input.focus();
                    input.select();
                } else {
                    // Input is still hidden, keep checking in the next frame
                    requestAnimationFrame(waitForVisibility);
                }
            };

            waitForVisibility();
        }
    }

    onSignerNameInputBlur () {
        this.state.canEditSignerName = false;
    }

    onChangeRoleName(name) {
        // Check if the new role name is different from the current one
        if (name && this.props.roleId && name !== this.state.roleName) {
            this.state.roleName = name;
            this.props.updateRoleName(this.props.roleId, this.state.roleName);
        }
    }

    onExpandSigner(id) {
        if (this.props.isCollapsed) {
            this.props.updateCollapse(id, false);
        }
    }

    async updateRoleNameAndAvatar(data) {
        this.state.roleName = data.name;
        const assignToId = data.assign_to?.id;
        if (assignToId) {
            const [partner] = await this.orm.call(
                "res.partner",
                "read",
                [[assignToId], ["avatar_128", "avatar_1920"]]
            );
            const avatar = partner.avatar_128 || partner.avatar_1920;
            if (avatar) {
                this.state.profilePic = this.getImageSrc(avatar);
            }
        } else {
            this.state.profilePic = "";
        }
    }

    async openSignRoleRecord() {
        this.dialog.add(FormViewDialog, {
            resId: this.props.roleId,
            resModel: "sign.item.role",
            size: "md",
            title: _t("Signer Settings"),
            onRecordSaved: async ({ data }) => {
                this.state.canEditSignerName=true;
                await this.updateRoleNameAndAvatar(data);
            },
        });
    }

    getImageSrc(assignTo) {
        if (!assignTo) {
            return
        }
        const magicChar = assignTo[0];
        const format = fileTypeMagicWordMap[magicChar] || "png";
        return `data:image/${format};base64,${assignTo}`;
    }

}
