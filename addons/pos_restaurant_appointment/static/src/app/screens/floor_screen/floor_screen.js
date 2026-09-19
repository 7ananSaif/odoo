import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { useSubEnv } from "@odoo/owl";
import { getMin } from "@point_of_sale/utils";
const { DateTime } = luxon;

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        useSubEnv({ position: {} });
    },
    async _createTableHelper() {
        const table = await super._createTableHelper(...arguments);
        const appointmentRessource = this.pos.models["appointment.resource"].get(
            table.appointment_resource_id?.id
        );

        if (!appointmentRessource) {
            await this.pos.data.searchRead(
                "appointment.resource",
                [["pos_table_ids", "in", table.id]],
                this.pos.data.fields["appointment.resource"],
                { limit: 1 }
            );
        }

        return table;
    },
    async duplicateFloor() {
        await super.duplicateFloor(...arguments);
        const tableIds = this.activeTables.map((table) => table.id);

        if (tableIds.length > 0) {
            await this.pos.data.searchRead(
                "appointment.resource",
                [["pos_table_ids", "in", tableIds]],
                this.pos.data.fields["appointment.resource"]
            );
        }
    },
    async createTableFromRaw(table) {
        delete table.appointment_resource_id;
        return super.createTableFromRaw(table);
    },

    getFirstAppointment(table) {
        if (!table.appointment_resource_id) {
            return false;
        }
        const appointments = this.pos.models["calendar.event"].getBy(
            "appointment_resource_ids",
            table.appointment_resource_id.id
        );
        if (!appointments) {
            return false;
        }
        const startOfToday = DateTime.now().set({ hours: 0, minutes: 0, seconds: 0 });
        appointments.map((appointment) => {
            if (appointment.start < startOfToday) {
                appointment.start = startOfToday;
            }
        });
        const dt_now = DateTime.now();
        const dt_tomorrow_ts = dt_now
            .plus({ days: 1 })
            .set({ hours: 0, minutes: 0, seconds: 0 }).ts;
        const possible_appointments = appointments.filter((a) => {
            const ts_now = dt_now - (a.duration / 2) * 3600000;
            const dt_ts = a.start.ts;
            return (
                dt_ts > ts_now &&
                dt_ts < dt_tomorrow_ts &&
                a.appointment_status !== "no_show" &&
                a.appointment_status !== "attended"
            );
        });
        if (possible_appointments.length === 0) {
            return false;
        }
        return getMin(possible_appointments, {
            criterion: (a) => a.start.ts,
        });
    },
    getFormattedDate(date) {
        return date.toFormat("HH:mm");
    },
    isCustomerLate(table) {
        const dateNow = DateTime.now();
        const dateStart = this.getFirstAppointment(table)?.start;
        return (
            dateNow > dateStart && this.getFirstAppointment(table).appointment_status === "booked"
        );
    },
    onClickAppointment(ev, table) {
        if (!this.pos.isEditMode) {
            ev.stopPropagation();
            return this.pos.editBooking(this.getFirstAppointment(table));
        }
    },
});
