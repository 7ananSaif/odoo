import { CalendarEvent } from "@pos_appointment/../tests/unit/data/calendar_event.data";

const { DateTime } = luxon;

CalendarEvent._records = [
    {
        id: 1,
        start: DateTime.now().toSQL(),
        duration: 4.0,
        stop: DateTime.now().plus({ hour: 4 }).toSQL(),
        name: "Test appointment",
        appointment_status: "booked",
        appointment_resource_ids: [1],
        total_capacity_reserved: 2,
    },
    {
        id: 2,
        start: DateTime.now().minus({ days: 1 }).toSQL(),
        duration: 4.0,
        stop: DateTime.now().minus({ days: 1 }).plus({ hours: 4 }).toSQL(),
        name: "Test appointment",
        appointment_status: "booked",
        appointment_resource_ids: [1],
        total_capacity_reserved: 2,
    },
    {
        id: 3,
        start: DateTime.now().toSQL(),
        duration: 2.0,
        stop: DateTime.now().plus({ hour: 4 }).toSQL(),
        name: "Test appointment",
        appointment_status: "attended",
        appointment_resource_ids: [2],
        total_capacity_reserved: 2,
    },
    {
        id: 4,
        start: DateTime.now().toSQL(),
        duration: 2.0,
        stop: DateTime.now().plus({ hour: 4 }).toSQL(),
        name: "Test appointment",
        appointment_status: "no_show",
        appointment_resource_ids: [2],
        total_capacity_reserved: 2,
    },
];
