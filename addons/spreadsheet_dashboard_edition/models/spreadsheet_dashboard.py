import json

from odoo import api, fields, models, _


class SpreadsheetDashboard(models.Model):
    _name = 'spreadsheet.dashboard'
    _inherit = ['spreadsheet.dashboard', 'spreadsheet.mixin']

    is_from_data = fields.Boolean(
        compute='_compute_is_from_data',
        compute_sudo=True,
        export_string_translation=False,
    )

    @api.depends('sample_dashboard_file_path')
    def _compute_is_from_data(self):
        # we guess that a dashboard is from data if it has a sample file path (only definable in XML)
        # and if it has an XML ID (so it is not created by a user)
        # This compute doesn't have the correct dependency on ir.model.data
        # to be recomputed automatically. But we don't really care as it's very unlikely to change
        # within the current request.
        xml_ids = self.env['ir.model.data'].search([
            ('model', '=', self._name),
            ('res_id', 'in', self.ids),
        ]).grouped('res_id')
        for dashboard in self:
            dashboard.is_from_data = bool(xml_ids.get(dashboard.id) and dashboard.sample_dashboard_file_path)

    def _get_spreadsheet_metadata(self, *args, **kwargs):
        return dict(
            super()._get_spreadsheet_metadata(*args, **kwargs),
            is_published=self.is_published,
            translation_namespace=self._get_dashboard_translation_namespace(),
        )

    def action_edit_dashboard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "action_edit_dashboard",
            "params": {
                "spreadsheet_id": self.id,
            },
        }

    def _get_serialized_readonly_dashboard(self):
        self.ensure_one()
        update_locale_command = {
            "type": "UPDATE_LOCALE",
            "locale": self.env["res.lang"]._get_user_spreadsheet_locale(),
        }
        self._check_collaborative_spreadsheet_access("read")
        revisions = self.sudo()._get_spreadsheet_serialized_revisions()
        revisions.append(json.dumps(self._build_new_revision_data([update_locale_command])))
        serialized_revisions = "[%s]" % ",".join(revisions)
        serialized_snapshot = self._get_spreadsheet_serialized_snapshot()
        metadata = self._get_spreadsheet_metadata()
        default_currency = metadata["default_currency"]
        translation_namespace = metadata["translation_namespace"]
        serialized_default_currency = json.dumps(default_currency, ensure_ascii=False)
        serialized_data = '{"snapshot": %s,"revisions": %s,"default_currency": %s,"translation_namespace": "%s"}' % (
            serialized_snapshot,
            serialized_revisions,
            serialized_default_currency,
            translation_namespace
        )
        return serialized_data

    def _dashboard_is_empty(self):
        self._check_collaborative_spreadsheet_access("read")
        all_revisions = self.sudo().with_context(active_test=False).spreadsheet_revision_ids
        return not len(all_revisions) and super()._dashboard_is_empty()

    def action_open_spreadsheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'action_edit_dashboard',
            'params': {
                'spreadsheet_id': self.id,
            }
        }

    @api.model
    def _get_spreadsheet_selector(self):
        if self.env.user.has_group('spreadsheet_dashboard.group_dashboard_manager'):
            return {
                "model": self._name,
                "display_name": _("Dashboards"),
                "sequence": 10,
                "allow_create": True,
            }
