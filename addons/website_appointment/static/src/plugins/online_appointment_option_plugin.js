import { Plugin } from "@html_editor/plugin";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { OnlineAppointmentOption } from "./online_appointment_option";
import { BuilderAction } from "@html_builder/core/builder_action";

class OnlineAppointmentOptionPlugin extends Plugin {
    static id = "OnlineAppointmentOption";
    static shared = [
        "setDatasetProperty",
        "getDatasetProperty",
        "getAllAppointmentTypesById",
        "fetchAppointmentTypes",
    ];

    setup() {
        this.fetchAppointmentTypesProm = null;
        this.allAppointmentTypesById = null;
    }

    resources = {
        builder_actions: {
            SetAppTypesAction,
            SetStaffUsersAction,
        },
        builder_options: [OnlineAppointmentOption],
        so_content_addition_selector: [".s_online_appointment"],
    };

    async fetchAppointmentTypes() {
        if (!this.fetchAppointmentTypesProm) {
            this.fetchAppointmentTypesProm = rpc("/appointment/get_snippet_data");
            this.allAppointmentTypesById = await this.fetchAppointmentTypesProm;
        }
        return this.fetchAppointmentTypesProm;
    }

    getAllAppointmentTypesById() {
        return this.allAppointmentTypesById;
    }

    /**
     * Set a target dataset attribute value and trigger cascading updates as
     * necessary. Finally, update the link's form unless prevented.
     *
     * @param {"targetTypes" | "appointmentTypes" | "targetUsers" | "staffUsers" } property
     * @param {String | number[]} value
     */
    setDatasetProperty(el, property, value) {
        if (property === "targetTypes") {
            // Change if all or a selection of appointment types. Reset all subsequent parameters
            if (this.getDatasetProperty(el, "targetTypes") !== value) {
                el.dataset.targetTypes = value;
                if (this.getDatasetProperty(el, "appointmentTypes", true).length) {
                    this.setDatasetProperty(el, "appointmentTypes", []);
                }
            }
            this.setDatasetProperty(el, "targetUsers", "all");
        } else if (property === "appointmentTypes") {
            el.dataset.appointmentTypes = JSON.stringify(value);
            this.setDatasetProperty(el, "targetUsers", "all");
        } else if (property === "targetUsers") {
            el.dataset.targetUsers = value;
            if (
                value !== "specify" ||
                this.getDatasetProperty(el, "appointmentTypes", true).length !== 1
            ) {
                this.setDatasetProperty(el, "staffUsers", []);
            }
        } else if (property === "staffUsers") {
            el.dataset.staffUsers = JSON.stringify(value);
        }
    }

    /**
     * Helper method to retrieve target dataset properties to increase other
     * methods' readability.
     *
     * @param {String} property Name of the target dataset property
     * @param {boolean} parsed `true` to apply JSON.parse before returning
     * @returns {(String | Number[])}
     */
    getDatasetProperty(el, property, parsed = false) {
        const value = el.dataset[property];
        return parsed ? JSON.parse(value) : value;
    }
}

export class SetAppTypesAction extends BuilderAction {
    static id = "setAppTypes";
    static dependencies = ["OnlineAppointmentOption"];
    apply({ editingElement, value }) {
        this.dependencies.OnlineAppointmentOption.setDatasetProperty(
            editingElement,
            "appointmentTypes",
            JSON.parse(value).map((appType) => appType.id)
        );
    }
    getValue({ editingElement }) {
        const selectedAppointmentTypes = this.dependencies.OnlineAppointmentOption.getDatasetProperty(
            editingElement,
            "appointmentTypes",
            true
        );
        const appointmentTypesDetails = selectedAppointmentTypes.map((id) => {
            const appointmentType = this.dependencies.OnlineAppointmentOption.getAllAppointmentTypesById()[id];
            return { id: appointmentType.id, name: appointmentType.name, display_name: appointmentType.name };
        });
        return JSON.stringify(appointmentTypesDetails);
    }
}

export class SetStaffUsersAction extends BuilderAction {
    static id = "setStaffUsers";
    static dependencies = ["OnlineAppointmentOption"];
    apply({ editingElement, value }) {
        this.dependencies.OnlineAppointmentOption.setDatasetProperty(
            editingElement,
            "staffUsers",
            JSON.parse(value).map((user) => user.id)
        );
    }
    getValue({ editingElement }) {
        const selectedAppointmentTypes = this.dependencies.OnlineAppointmentOption.getDatasetProperty(
            editingElement,
            "appointmentTypes",
            true
        );
        if (
            selectedAppointmentTypes.length !== 1 ||
            this.dependencies.OnlineAppointmentOption.getDatasetProperty(editingElement, "targetUsers") === "all"
        ) {
            return "[]";
        }
        const appointmentTypeData =
            this.dependencies.OnlineAppointmentOption.getAllAppointmentTypesById()[selectedAppointmentTypes[0]];
        const selectedUserIds = this.dependencies.OnlineAppointmentOption.getDatasetProperty(
            editingElement,
            "staffUsers",
            true
        );
        const staffUsersDetails = appointmentTypeData.staff_users
            .filter((user) => selectedUserIds.includes(user.id))
            .map(({ id, name }) => ({ id, name, display_name: name }));
        return JSON.stringify(staffUsersDetails);
    }
}

registry
    .category("website-plugins")
    .add(OnlineAppointmentOptionPlugin.id, OnlineAppointmentOptionPlugin);
