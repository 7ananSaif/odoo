from datetime import date

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, models, _


class MarketingCampaign(models.Model):
    _inherit = 'marketing.campaign'

    @api.model
    def get_campaign_templates_info(self):
        campaign_templates_info = super().get_campaign_templates_info()
        campaign_templates_info.update({
            'sales': {
                'label': _("eCommerce"),
                'templates': {
                    'anniversary': {
                        'title': _('Anniversary Discount'),
                        'description': _('Celebrate contacts that registered one year ago.'),
                        'icon': '/marketing_automation_website_sale/static/img/campaign_icons/cake.svg',
                        'function': '_get_marketing_template_anniversary',
                    },
                    'purchase_followup': {
                        'title': _('Purchase Follow-up'),
                        'description': _('Send an email to customers that bought a specific product after their purchase.'),
                        'icon': '/marketing_automation_website_sale/static/img/campaign_icons/cart.svg',
                        'function': '_get_marketing_template_purchase_followup',
                    },
                    'repeat_customer': {
                        'title': _('Create Repeat Customers'),
                        'description': _('Turn one-time visitors into repeat buyers.'),
                        'icon': '/marketing_automation_website_sale/static/img/campaign_icons/star.svg',
                        'function': '_get_marketing_template_repeat_customer',
                    },
                },
            }
        })
        return campaign_templates_info

    def _get_marketing_template_anniversary(self):
        anniversary_mailing_template = self.env.ref(
            'marketing_automation_website_sale.mailing_anniversary_arch',
            raise_if_not_found=False,
        )
        anniversary_arch = self.env['ir.ui.view']._render_template(
            anniversary_mailing_template.id,
        ) if anniversary_mailing_template else ''

        one_year_ago = date.today() - relativedelta(years=1)
        almost_one_year = one_year_ago + relativedelta(days=1)

        domain = [
            '&',
            ('create_date', '>=', one_year_ago.strftime('%Y-%m-%d')),
            ('create_date', '<', almost_one_year.strftime('%Y-%m-%d')),
        ]

        campaign = self.env['marketing.campaign'].create({
            'domain': repr(domain),
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'name': _('Anniversary Discount'),
        })
        anniversary_mailing = self.env['mailing.mailing'].create({
            'body_arch': anniversary_arch,
            'body_html': anniversary_arch,
            'mailing_model_id': self.env['ir.model']._get_id('res.partner'),
            'mailing_type': 'mail',
            'preview': _('✨ We have a surprise for you ✨'),
            'reply_to_mode': 'update',
            'subject': _('Happy non-birthday!'),
            'use_in_marketing_automation': True,
        })
        # Add a partner tag to the participants of any instance of this campaign
        anniversary_tag = self.env.ref(
            'marketing_automation_website_sale.res_partner_category_anniversary_discount_recipient',
            raise_if_not_found=False
        )
        if not anniversary_tag:
            anniversary_tag = self.env['res.partner.category'].create({
                'name': _("Anniversary Discount Coupon Recipient"),
            })
            self.env['ir.model.data'].create({
                'module': 'marketing_automation_website_sale',
                'name': 'res_partner_category_anniversary_discount_recipient',
                'model': anniversary_tag._name,
                'res_id': anniversary_tag.id,
            })
        server_action = self.env['ir.actions.server'].create({
            'evaluation_type': 'value',
            'model_id': self.env['ir.model']._get_id('res.partner'),
            'state': 'object_write',
            'name': _('Add Coupon Recipient Tag'),
            'resource_ref': f'res.partner.category,{anniversary_tag.id}',
            'update_m2m_operation': 'add',
            'update_path': 'category_id',
        })
        self.env['marketing.activity'].create({
            'activity_domain': '[]',
            'activity_type': 'email',
            'campaign_id': campaign.id,
            'interval_type': 'days',
            'interval_number': 0,
            'mass_mailing_id': anniversary_mailing.id,
            'name': _('Send Anniversary Email'),
            'trigger_type': 'begin',
            'child_ids': [
                (0, 0, {
                    'activity_type': 'action',
                    'campaign_id': campaign.id,
                    'interval_type': 'hours',
                    'interval_number': 8,
                    'name': _('Tag User With Promotion'),
                    'server_action_id': server_action.id,
                    'trigger_type': 'mail_open',
                }),
            ]
        })
        return campaign

    def _get_marketing_template_purchase_followup(self):
        campaign = self.env['marketing.campaign'].create({
            'name': _('Recent Purchase Follow-up'),
            'model_id': self.env['ir.model']._get_id('sale.order'),
            'domain': repr([('state', '=', 'sale'), ('team_id.website_ids', '!=', False)]),
        })
        followup_mailing_template = self.env.ref(
            'marketing_automation_website_sale.mailing_purchase_followup_arch',
            raise_if_not_found=False
        )
        # we need to pass in dynamic expressions otherwise it will try to render them at this stage...
        followup_arch = self.env['ir.ui.view']._render_template(
            followup_mailing_template.id,
            {'name_dynamic_expression': Markup('<t t-out="object.partner_id.name"></t>')}
        ) if followup_mailing_template else ''
        followup_mailing = self.env['mailing.mailing'].create({
            'subject': _('How is everything going?'),
            'body_arch': followup_arch,
            'body_html': followup_arch,
            'mailing_model_id': self.env['ir.model']._get_id('sale.order'),
            'reply_to_mode': 'update',
            'use_in_marketing_automation': True,
            'mailing_type': 'mail',
        })
        self.env['marketing.activity'].create({
            'trigger_type': 'begin',
            'activity_type': 'email',
            'interval_type': 'days',
            'mass_mailing_id': followup_mailing.id,
            'interval_number': 7,
            'name': _('How is everything going?'),
            'campaign_id': campaign.id,
        })
        return campaign

    def _get_marketing_template_repeat_customer(self):
        campaign = self.env['marketing.campaign'].create({
            'name': _('Create Repeat Customers'),
            'model_id': self.env['ir.model']._get_id('sale.order'),
            'domain': repr([
                ('state', '=', 'sale'),
                ('team_id.website_ids', '!=', False),
                ('amount_untaxed', '>=', 100),
            ])
        })
        purchase_mailing_template = self.env.ref(
            'marketing_automation_website_sale.mailing_repeat_customer_new_purchase_arch',
            raise_if_not_found=False
        )
        arrivals_mailing_template = self.env.ref(
            'marketing_automation_website_sale.mailing_repeat_customer_new_arrivals_arch',
            raise_if_not_found=False
        )
        purchase_arch = self.env['ir.ui.view']._render_template(purchase_mailing_template.id) if purchase_mailing_template else ''
        arrivals_arch = self.env['ir.ui.view']._render_template(arrivals_mailing_template.id) if arrivals_mailing_template else ''
        purchase_mailing = self.env['mailing.mailing'].create({
            'subject': _('Thank you for your purchase'),
            'body_arch': purchase_arch,
            'body_html': purchase_arch,
            'mailing_model_id': self.env['ir.model']._get_id('sale.order'),
            'reply_to_mode': 'update',
            'use_in_marketing_automation': True,
            'mailing_type': 'mail',
        })
        arrivals_mailing = self.env['mailing.mailing'].create({
            'subject': _('Check out these new arrivals!'),
            'body_arch': arrivals_arch,
            'body_html': arrivals_arch,
            'mailing_model_id': self.env['ir.model']._get_id('sale.order'),
            'reply_to_mode': 'update',
            'use_in_marketing_automation': True,
            'mailing_type': 'mail',
        })
        self.env['marketing.activity'].create({
            'trigger_type': 'begin',
            'activity_type': 'email',
            'interval_type': 'days',
            'mass_mailing_id': purchase_mailing.id,
            'interval_number': 0,
            'name': _('Purchase Thanks'),
            'campaign_id': campaign.id,
            'child_ids': [
                (0, 0, {
                    'trigger_type': 'mail_open',
                    'activity_type': 'email',
                    'interval_type': 'weeks',
                    'mass_mailing_id': arrivals_mailing.id,
                    'interval_number': 1,
                    'name': _('New Arrivals'),
                    'campaign_id': campaign.id,
                }),
            ]
        })
        return campaign
