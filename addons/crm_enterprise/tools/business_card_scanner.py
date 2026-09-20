# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests

from odoo import _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.urls import urljoin as url_join

_logger = logging.getLogger(__name__)

PROMPT = (
    "Extract details from the provided business card image as a JSON object. "
    "I will use the response you give me to extract data in an automated process so respect instructions or else it will fail. "
    "I will specify a list of the information I need, do NOT add anything else."
    "Consider this request with a very low temperature, DO NOT GUESS or try to be creative, only use the text you can read on the image, do not make things up! "
    "I don't want to see anything like 'Not specified' or 'Unknown' in the resulting JSON, don't specify the fields if you don't know. "
    "If you do not have AT LEAST a 'contact_name' OR a 'company_name', return an empty JSON. "
    "Reply with ONLY the JSON object on a SINGLE LINE, without code editor or styling. "
    "Here are the information I need, the field name in your resulting JSON is specified each time between quotes: "
    "- The name of the company, as 'partner_name' "
    "- The name of the contact (the person), as 'contact_name' "
    "- The main phone number (only ONE), as 'phone' "
    "- The main email address (only ONE), as 'email_from' "
    "- The company or contact website (only ONE), as 'website' "
    "- The Job Position, as 'function' "
    "- The city as 'city' "
    "- The zip code as 'zip' "
    "- The state code as 'state_code', it needs to be a code and not the full name (example: Q1 for London), if you don't know the code, don't specify this field "
    "- The country code as 'country_code', in a 2 characters ISO code (NOT 3 characters, 2), if you don't know the ISO code, don't specify this field "
    "- The first part of the address that is not in the above fields, usually the street and number, as 'street' "
    "- The second part of the address, only if it is obvious there are 2 parts, as 'street2' "
)


class BusinessCardScanner:

    def __init__(self, env):
        self.env = env

    def business_cards_to_leads(self, attachments):
        """ Create opportunities from the details extracted from images of business cards. """

        openai_api_key = self.env["ir.config_parameter"].sudo().get_param("crm_enterprise.business_card_reader.openai_key")

        valid_attachments = []
        lead_values_list = []

        session = False
        if openai_api_key:
            session = requests.Session()  # re-usable session to batch requests

        for attachment in attachments:
            image_url = f"{attachment.get_base_url()}/web/image/{attachment.id}?access_token={attachment.access_token}"

            try:
                if openai_api_key:
                    extracted_data = self._ocr_from_openai(image_url, openai_api_key, session)
                else:
                    extracted_data = self._ocr_from_iap(image_url)
            except requests.exceptions.RequestException:
                raise UserError(_("Network error while processing the business cards."))

            if not extracted_data:
                continue

            # Normalize to list of dicts
            if isinstance(extracted_data, dict):
                extracted_data = [extracted_data]

            fields_allowlist = [
                'partner_name',
                'contact_name',
                'email_from',
                'phone',
                'website',
                'function',
                'street',
                'street2',
                'zip',
            ]

            for data in extracted_data:
                lead_values = {
                    field: data[field].strip()
                    for field in fields_allowlist
                    if data.get(field)
                }
                lead_values['type'] = 'opportunity'

                contact_name = lead_values.get('contact_name')
                company_name = lead_values.get('partner_name')
                if contact_name or company_name:
                    lead_values['name'] = _("%(contact_name)s's opportunity", contact_name=contact_name or company_name)
                else:
                    continue  # safety net as we told AI to return an empty result in this case

                # extract country
                country = False
                if data.get('country_code') and len(data['country_code']) == 2:
                    country = self.env['res.country'].search([('code', '=', data['country_code'])], limit=1)
                    if country:
                        lead_values['country_id'] = country.id

                # extract state
                if data.get('state_code'):
                    domain = Domain('code', '=', data['state_code'])
                    if country:
                        domain &= Domain('country_id', '=', country.id)
                    state = self.env['res.country.state'].search(domain, limit=1)
                    if state:
                        lead_values['state_id'] = state.id

                # format phone
                if lead_values.get('phone'):
                    lead_values['phone'] = self.env['crm.lead']._phone_format(
                        number=lead_values['phone'],
                        country=country,
                    )

                lead_values_list.append(lead_values)
                valid_attachments.append(attachment)

        if len(attachments) == 1 and not lead_values_list:
            # special case when a single attachment fails: do not create records
            # caller is responsible for followup behavior and feedback in that case
            return self.env['crm.lead']

        leads = self.env['crm.lead'].create(lead_values_list)
        for lead, attachment in zip(leads, valid_attachments):
            attachment.write({
                'res_model': 'crm.lead',
                'res_id': lead.id
            })

            lead._message_log(
                body=_('Lead generated from this image.'),
                attachment_ids=[attachment.id],
            )

        # create "empty leads" for failing images to give better user feedback
        invalid_attachments = attachments.filtered(lambda attachment: attachment not in valid_attachments)
        empty_leads = self.env['crm.lead'].create([{
            'name': _('New Lead Scan')
        } for i in range(len(invalid_attachments))])
        for lead, attachment in zip(empty_leads, invalid_attachments):
            attachment.write({
                'res_model': 'crm.lead',
                'res_id': lead.id
            })

            lead._message_log(
                body=_('Could not extract lead information from this image.'),
                attachment_ids=[attachment.id],
            )

        return leads + empty_leads

    def _ocr_from_openai(self, image_url, api_key, session):
        response = session.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "user", "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]}
                ],
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            timeout=20,
        )

        if response.ok:
            response_content = response.json()
            result = response_content['choices'][0]['message']['content']
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                _logger.warning('openAI returned non-parsable response: %s', response.text)
                return {}
        else:
            _logger.warning('openAI failure: %s', response.text)
            raise UserError(
                _("Oops, the AI service is not working 🤖. Please contact your administrator to verify settings.")
            )

    def _ocr_from_iap(self, image_url):
        IrConfigParameter = self.env["ir.config_parameter"].sudo()
        olg_api_endpoint = IrConfigParameter.get_param(
            "html_editor.olg_api_endpoint", "https://olg.api.odoo.com"
        )
        database_id = IrConfigParameter.get_param("database.uuid")
        response = iap_tools.iap_jsonrpc(
            url_join(olg_api_endpoint, "/api/olg/1/chat"),
            params={
                "prompt": PROMPT,
                "conversation_history": [
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {
                            "url": image_url}
                        }
                    ]}
                ],
                "database_id": database_id,
            },
            timeout=20,
        )
        if response['status'] != 'success':
            return {}  # nothing to log in this case, IAP provides 0 info

        result = response['content']
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            _logger.warning('IAP returned non-parsable response: %s', result)
            return {}
