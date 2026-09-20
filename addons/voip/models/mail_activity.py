from collections import defaultdict

from odoo import api, fields, models

from odoo.addons.mail.tools.discuss import Store


class MailActivity(models.Model):
    _name = "mail.activity"
    _inherit = ["mail.activity", "voip.country.code.mixin"]

    phone = fields.Char("Phone", compute="_compute_phone", readonly=False, store=True)

    @api.depends("res_model", "res_id", "activity_type_id")
    def _compute_phone(self):
        call_activities = self.filtered(
            lambda activity: activity.id
            and activity.res_model
            and activity.res_id
            and activity.activity_category == "phonecall"
        )
        (self - call_activities).phone = False
        phone_numbers_by_activity = call_activities._get_phone_numbers_by_activity()
        for activity in call_activities:
            activity.phone = phone_numbers_by_activity.get(activity, False)

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        call_activities = activities.filtered(
            lambda activity: activity.phone and activity.user_id and activity.activity_category == "phonecall"
        )
        call_activities.user_id._bus_send("refresh_call_activities", {})
        return activities

    def write(self, vals):
        if "date_deadline" in vals and self.user_id:
            call_activities = self.filtered(
                lambda activity: activity.phone and activity.user_id and activity.activity_category == "phonecall"
            )
            call_activities.user_id._bus_send("refresh_call_activities", {})
        return super().write(vals)

    @api.model
    @api.readonly
    def get_today_call_activities(self):
        """Retrieve the list of activities that:
          * have the type “phonecall”
          * have a phone number
          * are overdue
          * are assigned to the current user
          * are in the current company or free of document

        The resulting list is intended for display in the “Activities” tab.
        """
        overdue_call_activities_of_current_user = self.search(
            [
                ("activity_type_id.category", "=", "phonecall"),
                ("user_id", "=", self.env.uid),
                ("date_deadline", "<=", fields.Date.today()),
                ("phone", "!=", False),
            ]
        )
        record_ids_by_model_name = defaultdict(set)
        for activity in overdue_call_activities_of_current_user.filtered("res_model"):
            record_ids_by_model_name[activity.res_model].add(activity.res_id)

        allowed_record_ids_by_model_name = defaultdict(list)
        for model_name, record_ids in record_ids_by_model_name.items():
            if not self.env[model_name].has_access("read"):
                continue
            # calling search will filter out records that are irrelevant to the current company
            allowed_record_ids_by_model_name[model_name] = self.env[model_name].search([("id", "in", list(record_ids))]).ids
        store = Store()
        overdue_call_activities_of_current_user.filtered(
            lambda activity: not activity.res_model or activity.res_id in allowed_record_ids_by_model_name[activity.res_model]
        )._format_call_activities(store)
        return store.get_result()

    def _action_done(self, feedback=False, attachment_ids=None):
        """Extends _action_done to notify the user assigned to a phonecall
        activity that it has been marked as done. This is useful to trigger the
        refresh of the “Next Activities” tab.
        """
        self.filtered(
            lambda activity: activity.activity_type_id.category == "phonecall"
        ).user_id._bus_send("refresh_call_activities", {})
        return super()._action_done(feedback=feedback, attachment_ids=attachment_ids)

    def _format_call_activities(self, store: Store):
        """Serializes call activities for transmission to/use by the client side."""
        call_activities = self.filtered(lambda activity: activity.activity_type_id.category == "phonecall")
        for model_name, activities in call_activities.grouped("res_model").items():
            if model_name:
                records = self.env[model_name].browse(activities.mapped("res_id"))
                partners_by_records = records._mail_get_partners(introspect_fields=True)
            else:
                partners_by_records = {}
            # Store all the partner at once to avoid O(n) queries in the loop
            partner_ids = [p[0].id for p in partners_by_records.values() if p]
            store.add(self.env["res.partner"].browse(partner_ids))
            for activity in activities:
                partners = partners_by_records.get(activity.res_id, self.env["res.partner"])
                store.add(activity, [
                    "id",
                    "res_name",
                    "phone",
                    "res_id",
                    "res_model",
                    "state",
                    "summary",
                    "date_deadline",
                    "mail_template_ids",
                    "activity_category",
                    Store.One("phone_country_id", activity.phone_country_id._voip_get_store_fields()),
                    Store.One("user_id", Store.One("partner_id")),
                    Store.Attr("partner", Store.One(partners[:1], partners._voip_get_store_fields()))
                ])

    def _get_phone_numbers_by_activity(self):
        """Batch compute the phone numbers associated with the activities.

        :return: phone number for each activity (obtained from the activity itself or from the related partner);
        """
        phone_numbers_by_activity = {}
        data_by_model = self.filtered("res_model")._classify_by_model()
        for model, data in data_by_model.items():
            records = self.env[model].browse(data["record_ids"])
            for record, activity in zip(records, data["activities"]):
                phone = record.phone if "phone" in record else False
                if not phone:
                    recipient = next(
                        iter(record._mail_get_partners(introspect_fields=True)[record.id]),
                        self.env["res.partner"],
                    )
                    phone = recipient.phone
                phone_numbers_by_activity[activity] = phone
        return phone_numbers_by_activity

    def _to_store_defaults(self, target):
        return [*super()._to_store_defaults(target), "phone"]
