import { Component, toRaw, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { FileUploader } from "@web/views/fields/file_handler";
import { formatPercentage } from "@web/views/fields/formatters";

export class HolderEditDialog extends Component {
    static template = "equity.HolderEditDialog";
    static components = { Dialog, FileUploader };
    static props = {
        isNew: { type: Boolean },
        ubo: { type: Object },
        addUbo: { type: Function },
        close: { type: Function },
        allCountries: { type: Object },
        equityUboSettings: { type: Object },
    };

    setup() {
        this.notification = useService("notification");
        this.controlMethods = this.props.equityUboSettings.control_methods;
        this.activatePercentages = this.props.equityUboSettings.activate_percentages;
        this.activateRole = this.props.equityUboSettings.activate_role;
        this.authRepRoles = this.props.equityUboSettings.auth_rep_roles;

        this.state = useState({
            ubo: this.props.ubo,
            newUbo: structuredClone(toRaw(this.props.ubo)),
        });
    }

    formatPercentage(value) {
        return formatPercentage(value, { noSymbol: 1 });
    }

    onchangeCountryId(ev) {
        this.state.newUbo.holder_id.country_id = parseInt(ev.target.value) || false;
    }

    onchangeControlMethod(ev) {
        this.state.newUbo.ownership = 0;
        this.state.newUbo.voting_rights = 0;
        this.state.newUbo.auth_rep_role = false;

        if (this.showPercentages) {
            this.state.newUbo.ownership = this.props.ubo.ownership * 100;
            this.state.newUbo.voting_rights = this.props.ubo.voting_rights * 100;
        }
        if (this.showRole) {
            this.state.newUbo.auth_rep_role = this.props.ubo.auth_rep_role;
        }
    }

    onchangeOwnership(ev) {
        const newValue = ev.target.value / 100;
        this.state.newUbo.ownership = newValue;
        this.state.newUbo.voting_rights = newValue;
    }

    onchangeVotingRights(ev) {
        const newValue = ev.target.value / 100;
        this.state.newUbo.voting_rights = newValue;
    }

    onFileUpload(file) {
        this.state.newUbo.attachment = file;
    }

    onFileRemove() {
        this.state.newUbo.attachment = null;
    }

    confirm() {
        if (this.submitErrors.length) {
            for (const submitError of this.submitErrors) {
                this.notification.add(submitError, { type: "danger", autocloseDelay: 10000, });
            }
            return;
        }

        if (this.props.isNew) {
            this.props.addUbo(this.state.newUbo);
        } else {
            Object.assign(this.state.ubo, this.state.newUbo);
        }
        this.props.close();
    }

    get showPercentages() {
        return this.activatePercentages.includes(this.state.newUbo.control_method);
    }

    get showRole() {
        return this.activateRole.includes(this.state.newUbo.control_method);
    }

    get submitErrors() {
        const errors = [];
        if (!this.state.newUbo.holder_id.name) {
            errors.push(_t("Name is mandatory"));
        }
        if (!this.state.newUbo.start_date) {
            errors.push(_t("Control Start Date is mandatory"));
        }
        if (!this.state.newUbo.holder_id.ubo_birth_date && !this.state.newUbo.holder_id.ubo_national_identifier) {
            errors.push(_t("You must provide either the date of birth, or the ID number"));
        }
        if (this.invalidPercentages) {
            errors.push(_t("please keep percentages between 0 and 100"));
        }
        return errors;
    }

    get invalidPercentages() {
        const ownership = parseFloat(this.state.newUbo.ownership) || 0;
        const votingRights = parseFloat(this.state.newUbo.voting_rights) || 0;
        return ownership < 0 || ownership > 1 ||
            votingRights < 0 || votingRights > 1;
    }

    get title() {
        if (this.props.isNew) {
            return _t("Add Beneficial Owner");
        } else {
            return _t("Edit Beneficial Owner");
        }
    }
}
