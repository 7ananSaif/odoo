from odoo import models, api, _
from odoo.fields import Domain
from odoo.addons.website_appointment.controllers.appointment import WebsiteAppointment


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_hardcoded_sample(self, model):
        if model._name != 'appointment.type':
            return super()._get_hardcoded_sample(model)

        return [{
            'message_intro': _("A first step in joining our team as a technical consultant."),
            'name': _('Candidate Interview'),
        }, {
            'name': _('Online Cooking Lesson'),
        }, {
            'name': _('Tennis Court'),
        }]

    def _prepare_values(self, limit=None, search_domain=None, **options):
        if self.model_name == 'appointment.type':
            if country := WebsiteAppointment._get_customer_country():
                customer_country_domain = Domain('country_ids', 'in', [False, country.id])
                search_domain = Domain(search_domain or Domain.TRUE) & customer_country_domain
        return super()._prepare_values(limit=limit, search_domain=search_domain, **options)

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if 'field_names' in defaults and self.env.context.get('model') == 'appointment.type':
            defaults['field_names'] = 'name,category'
        return defaults
