import hashlib
import json
import requests
import uuid

from urllib.parse import urlencode

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request

TOKEN_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/access_token",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/access_token",
    'disabled': "",
}
AUTH_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/authorize",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/authorize",
    'disabled': "",
}
IAP_ENDPOINT = {
    'test': "https://l10n-be-intervat.test.odoo.com/api/l10n_be_intervat/1",
    'prod': "https://l10n-be-intervat.api.odoo.com/api/l10n_be_intervat/1",
    'disabled': "",
}


class L10nBeIntervatController(http.Controller):
    @http.route('/l10n_be_intervat/callback', type='http', auth='user')
    def callback(self, **kwargs):
        state = json.loads(kwargs.get('state', '{}'))
        if kwargs.get('error') or not kwargs.get('code'):
            request.env.user._bus_send('simple_notification', {
                'type': 'danger',
                'title': request.env._("Authentication Failed"),
                'message': f"{kwargs['error']}: {kwargs['error_description']}",
                'sticky': True,
            })
        else:
            company_id = request.env['res.company'].browse(state.get('company_id'))
            return_id = request.env['account.return'].browse(state.get('return_id'))
            response = requests.post(
                url=TOKEN_ENDPOINT[company_id.l10n_be_intervat_mode],
                data={
                    'grant_type': 'authorization_code',
                    'redirect_uri': f"{IAP_ENDPOINT[company_id.l10n_be_intervat_mode]}/callback",
                    'code': kwargs.get('code'),
                    'code_verifier': company_id.l10n_be_intervat_code_verifier,
                    'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                    'client_assertion': company_id._l10n_be_generate_jwt(),
                    'client_id': 'odoo',
                },
                headers={
                    'accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )
            response_json, error = company_id._l10n_be_get_error_from_response(response)
            if error:
                return_id._message_log(body=self.env._("Authentication Error: \n") + error['error_message'])
                request.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'title': request.env._("Authentication Failed"),
                })
                return request.redirect(state.get('referrer_url', '/web'))

            company_id._l10n_be_verify_id_token_signature(response_json['id_token'])

            company_id.l10n_be_intervat_access_token = response_json['access_token']
            company_id.l10n_be_intervat_refresh_token = response_json['refresh_token']
            company_id.l10n_be_intervat_last_call_date = fields.Datetime.now()

            request_type = state.get('request_type')
            notification_message = request.env._("Send your declaration now.")
            submission_error = False
            try:
                if request_type == 'submit':
                    submission_error = return_id._l10n_be_submit_xml() == 'error'
                    notification_message = request.env._("Your declaration has been sent.")
                elif request_type == 'fetch':
                    return_id.l10n_be_action_fetch_from_intervat()
                    notification_message = request.env._("Your declaration has been fetched.")
            except UserError as e:
                error_title = request.env._("Fetching Error: \n") if request_type == 'fetch' else request.env._("Submission Error: \n")
                error_message = error_title + "\n".join(e.args)
                return_id._message_log(body=error_message)
                request.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'title': error_title,
                })
                return request.redirect(state.get('referrer_url', '/web'))

            if submission_error:
                request.env.user._bus_send('simple_notification', {
                    'type': 'success',
                    'title': request.env._("Authentication Successful"),
                    'message': notification_message,
                })

        return request.redirect(state.get('referrer_url', '/web'))

    @http.route('/l10n_be_intervat/authorize/<int:company_id>/<int:return_id>/<string:request_type>', auth='user')
    def authorize(self, company_id, return_id, request_type):
        company = http.request.env['res.company'].browse(company_id)

        state = {
            'company_id': company.id,
            'return_id': return_id,
            'request_type': request_type,
            'referrer_url': request.httprequest.referrer,
            'company_token': hashlib.sha256(company.l10n_be_intervat_certificate_id.l10n_be_intervat_jwk_token.encode()).hexdigest(),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
        }

        auth_url_params = urlencode({
            'response_type': 'code',
            'client_id': 'odoo',
            'redirect_uri': f"{IAP_ENDPOINT[company.l10n_be_intervat_mode]}/callback",
            'code_challenge_method': 'S256',
            'code_challenge': company.l10n_be_intervat_code_challenge,
            'scope': 'openid profile documents-read-api vat-manage-api',
            'claims': json.dumps({"ecb": company.company_registry}).encode(),
            'nonce': f'{uuid.uuid4()}',
            'state': json.dumps(state).encode(),
        })
        auth_url = f'{AUTH_ENDPOINT[company.l10n_be_intervat_mode]}?{auth_url_params}'
        return request.redirect(auth_url, code=302, local=False)
