from odoo import models, api, fields


class L10n_AuAuditLoggingMixin(models.AbstractModel):
    _name = "l10n_au.audit.logging.mixin"
    _description = "Mixin for Audit Logging in Australia"

    @api.model
    def _get_display_name_fields(self):
        return ["display_name"]

    def _get_display_name(self):
        """
        Returns the display name of the record.
        Override this method in subclasses to provide a custom display name.
        """
        return " - ".join(self[field] for field in self._get_display_name_fields() if self[field]) + f" (model: {self._name}, id:{self.id})"

    def _get_audit_logging_fields(self):
        """
        Returns a list of fields to be logged for audit purposes.
        Override this method in subclasses to specify the fields to be logged.
        """
        return []

    def _records_to_log(self):
        """
        Returns a list of records to be logged for audit purposes.
        Override this method in subclasses to specify the records to be logged.
        """
        return self.filtered(lambda r: r.country_code == "AU")

    def _create_audit_logs(self, fields_to_log, before_groups=None, after_groups=None):
        """ Log the changes to the specified fields for the records in self.
            fields_to_log: List of field names to be logged
            before_groups: Dict of groups before the change (only for res.users and group_ids field)
            after_groups: Dict of groups after the change (only for res.users and group_ids field)
        """
        logs_to_create = []
        for record in self:
            for field_name in fields_to_log:
                # Determine the company context for logging
                company = self.env.company
                if record._name == "res.company":
                    company = record

                if record._name == "res.users" and field_name == "group_ids":
                    groups_added = after_groups[record.id] - before_groups[record.id]
                    groups_removed = before_groups[record.id] - after_groups[record.id]

                    for group in groups_added:
                        logs_to_create.append({
                            "log_description": f"{fields.Datetime.now()} - {company.l10n_au_bms_id} - {company.name} - User {record._get_display_name()} was granted access to group {group.display_name} by {self.env.user.display_name}"
                        })

                    for group in groups_removed:
                        logs_to_create.append({
                            "log_description": f"{fields.Datetime.now()} - {company.l10n_au_bms_id} - {company.name} - User {record._get_display_name()} was removed from group {group.display_name} by {self.env.user.display_name}"
                        })
                else:
                    logs_to_create.append({
                        "company_id": company.id,
                        "log_description": f"{fields.Datetime.now()} - {company.l10n_au_bms_id} - {company.name} - {record._fields[field_name].string} was changed for {record._get_display_name()} by {self.env.user.display_name}"
                    })
        self.env["l10n_au.audit.log"].sudo().create(logs_to_create)

    def write(self, vals):
        records_to_log = self._records_to_log()

        if not records_to_log:
            return super().write(vals)

        fields_to_log = vals.keys() & self._get_audit_logging_fields()
        if fields_to_log:
            records_to_log._create_audit_logs(fields_to_log)
        # Get the groups before and after values for a user and it needs to handled for both res.users and res.groups
        if self._name == "res.users" and "group_ids" in vals:
            before_groups = {rec.id: rec.group_ids for rec in records_to_log}
        # Log from res.groups the same as when write is triggered on res.user
        elif self._name == "res.groups" and "user_ids" in vals:
            users_changed = self.env["res.users"].browse(vals.get("user_ids")[0][2])._records_to_log()
            before_groups = {user.id: user.group_ids for user in users_changed}

        res = super().write(vals)

        if self._name == "res.users" and "group_ids" in vals:
            after_groups = {rec.id: rec.group_ids for rec in records_to_log}
            records_to_log._create_audit_logs(["group_ids"], before_groups=before_groups, after_groups=after_groups)
        # _create_audit_logs is called on the users so the same logic can be reused
        elif self._name == "res.groups" and "user_ids" in vals:
            after_groups = {user.id: user.group_ids for user in users_changed}
            users_changed._create_audit_logs(["group_ids"], before_groups=before_groups, after_groups=after_groups)

        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records_to_log = records._records_to_log()
        if records_to_log:
            records_to_log._create_audit_logs(records_to_log._get_audit_logging_fields())
            if self._name == "res.users":
                after_groups = {rec.id: rec.group_ids for rec in records_to_log}
                records_to_log._create_audit_logs(["group_ids"], before_groups={rec.id: self.env["res.groups"] for rec in records_to_log}, after_groups=after_groups)
        return records
