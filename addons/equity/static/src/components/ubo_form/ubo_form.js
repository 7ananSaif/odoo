import { HolderEditDialog } from "@equity/components/ubo_form/holder_edit_dialog";
import { HolderEndDialog } from "@equity/components/ubo_form/holder_end_dialog";
import { Component, markup, useState } from "@odoo/owl";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatPercentage } from "@web/views/fields/formatters";


export class UboForm extends Component {
    static template = "equity.UboForm";
    static props = {
        accessToken: { type: String },
        ubos: { type: Array },
        equityUboSettings: { type: Object },
        allCountries: { type: Array },
        defaultCountryId: { type: Number },
    };

    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.notification = useService("notification");

        this.ubos = useState(this.props.ubos);
        this.allCountries = Object.fromEntries(this.props.allCountries.map(({ id, name }) => [id, name]));
    }

    formatPercentage(value, controlMethod) {
        const activatePercentages = this.props.equityUboSettings.activate_percentages.includes(controlMethod);
        if (activatePercentages) {
            return formatPercentage(value);
        }
        return "";
    }

    holderEdit(uboIndex) {
        const newUbo = {
            control_method: "co_1",
            ownership: 0,
            voting_rights: 0,
            auth_rep_role: false,
            start_date: false,
            end_date: false,
            attachment_expiration_date: false,
            holder_id: {
                name: "",
                country_id: this.props.defaultCountryId,
                ubo_birth_date: false,
                ubo_national_identifier: "",
                ubo_pep: false,
            },
        };
        this.dialogService.add(HolderEditDialog, {
            isNew: isNaN(uboIndex),
            ubo: isNaN(uboIndex) ? newUbo : this.ubos[uboIndex],
            addUbo: (ubo) => this.ubos.push(ubo),
            close: () => { },
            allCountries: this.allCountries,
            equityUboSettings: this.props.equityUboSettings,
        });
    }

    holderEnd(uboIndex) {
        this.dialogService.add(HolderEndDialog, { ubo: this.ubos[uboIndex], close: () => { } });
    }

    holderEnded(uboIndex) {
        return Boolean(this.ubos[uboIndex]["end_date"]);
    }

    holderReturn(uboIndex) {
        this.ubos[uboIndex]["end_date"] = false;
    }

    displayDate(dateString) {
        if (!dateString) {
            return "";
        }
        return formatDate(deserializeDate(dateString), { format: "MMM d, yyyy" });
    }

    styleTitleAndContent(title, content, classes = "") {
        return markup`<div class="${classes}">
            <p class="mb-0">${title}</p>
            <p class="text-muted mb-0">${content}</p>
        </div>`;
    }

    async submit(ev) {
        const form = ev.target.form;
        if (!form.checkValidity()) {
            return form.reportValidity();
        }
        const res = await rpc("/my/ubo/submit/data", { access_token: this.props.accessToken, data: this.ubos });
        if (!res) {
            form.submit();
        } else {
            this.notification.add(res["error"], { type: "danger" });
        }
    }

    get headers() {
        return [
            _t("Name"),
            _t("Control Start Date"),
            _t("Control End Date"),
            _t("Control Method"),
            _t("Ownership"),
            _t("Voting Rights"),
            "",
        ];
    }

    get numericRowsIndices() {
        return [4, 5];
    }

    get rows() {
        return this.ubos.sort((a, b) => {
            const aHasEnd = Boolean(a.end_date);
            const bHasEnd = Boolean(b.end_date);

            if (aHasEnd && !bHasEnd) return 1;
            if (!aHasEnd && bHasEnd) return -1;

            return 0;
        }).map((ubo) => {
            return [
                this.styleTitleAndContent(ubo["holder_id"]["name"], this.displayDate(ubo["holder_id"]["ubo_birth_date"])),
                this.displayDate(ubo["start_date"]),
                this.displayDate(ubo["end_date"]),
                this.styleTitleAndContent(
                    this.props.equityUboSettings.control_methods[ubo["control_method"]],
                    this.props.equityUboSettings.auth_rep_roles[ubo["auth_rep_role"]],
                ),
                this.formatPercentage(ubo["ownership"], ubo["control_method"]),
                this.formatPercentage(ubo["voting_rights"], ubo["control_method"]),
            ];
        });
    }
}

registry.category("public_components").add("equity.UboForm", UboForm);
