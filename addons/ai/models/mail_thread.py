# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class MailThread(models.AbstractModel):
    _name = 'mail.thread'
    _inherit = ['mail.thread']

    def _ai_serialize_activities_data(self):
        """Serialize planned activities data for AI context"""
        if not hasattr(self, 'activity_ids'):
            return ""
        activities_data = []
        for activity in self.activity_ids:
            activity_info = f"Activity: {activity.activity_type_id.name}"
            if activity.summary:
                activity_info += f" - {activity.summary}"
            activity_info += f" (Due: {activity.date_deadline}, Assigned to: {activity.user_id.name}, Status: {activity.state})"
            if activity.note:
                # Strip HTML tags from note and limit length
                note_text = activity.note.striptags().strip() if activity.note else ''
                if note_text:
                    activity_info += f" - Note: {note_text}"
            activities_data.append(activity_info)
        return " | ".join(activities_data) if activities_data else ""

    def _ai_serialize_messages_data(self):
        chatter_messages = []
        for message in self.message_ids:
            chatter_messages.append(
                f"({message.subtype_id.name}) {message.author_id.name}: {message.body.striptags().strip() if message.body else ''}, "
            )
        # the messages are stored from newest to oldest - reverse them so they are formatted like the conversation history
        chatter_messages = " ".join(list(reversed(chatter_messages)))
        activities_data = self._ai_serialize_activities_data()
        if activities_data:
            chatter_messages += f" Additionally, this chatter has the following planned activities: {activities_data}"

        return chatter_messages

    def _ai_initialise_context(
        self, caller_component, text_selection=None, front_end_info=None
    ):
        context = super()._ai_initialise_context(
            caller_component, text_selection, front_end_info
        )

        # If required, pass the previous chatter messages to the model's context
        if caller_component != "html_field_text_select":
            context.insert(
                -2,  # we insert the message at this index in order for the chatter conversation to be added right after the records info JSON
                f"The odoo record, from which you were called, can also have associated correspondance tied to it. All those messages and notes are included in the chatter, a chat-like area in the record's form view. The previous chatter correspondance, from oldest to newest, for this record is this: {self._ai_serialize_messages_data()}",
            )

        return context
