import requests
import logging
import uuid
from odoo import _
from contextlib import contextmanager
from odoo.addons.iap import jsonrpc
from odoo.exceptions import ValidationError
from ...pos_enterprise.models.data_validator import object_of, list_of

_logger = logging.getLogger(__name__)

auth_schema = object_of({
    'api_key': True,
    'api_secret': True,
})
fon_schema = object_of({
    'fon_participant_id': True,
    'fon_user_id': True,
    'fon_user_pin': True
})
scu_schema = object_of({
    'legal_entity_id': object_of({
        'vat_id': True,
    })
})
sign_order_schema = object_of({
    'schema': object_of({
        'ekabs_v0': object_of({
            'head': object_of({
                'number': True,
                'date': True,
                'seller': object_of({
                    'name': True,
                    'tax_number': True,
                    'address': True,
                }),
                'buyer': object_of({
                    'name': True,
                    'address': True,
                }),
            }),
            'data': object_of({
                'currency': True,
                'full_amount_incl_vat': True,
                'payment_types': list_of(object_of({
                    'name': True,
                    'amount': True,
                })),
                'vat_amounts': list_of(object_of({
                    'vat_rate': True,
                    'percentage': True,
                    'incl_vat': True,
                    'excl_vat': True,
                    'vat': True,
                })),
                'lines': list_of(object_of({
                    'text': True,
                    'vat_amounts': list_of(object_of({
                        'percentage': True,
                        'incl_vat': True
                    })),
                    'item': object_of({
                        'number': True,
                        'quantity': True,
                        'price_per_unit': True
                    })
                }))
            }),
        }),
    }),
    'receipt_type': True,
})


class FiskalyClient:

    def __init__(self, company, api_key, api_secret, version=1):
        self.base_url = f"https://rksv.fiskaly.com/api/v{version}/"
        # Company is here just in case there is a need to refresh the token
        self.company = company
        self.api_key = api_key
        self.api_secret = api_secret

    @contextmanager
    def _make_session(self, bearer_token):
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {bearer_token}'
        })
        retry = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(
            total=3,
            status_forcelist=[400, 403, 404],  # Exclude 401 as we handle it specially
        ))
        session.mount('https://', retry)

        def request(method, endpoint, data=None, params=None):
            url = self.base_url + endpoint
            try:
                resp = session.request(method, url, json=data, params=params, timeout=5)

                # Handle 401 Unauthorized specially - to refresh the token and retry
                if resp.status_code == 401:
                    _logger.info("Token expired, attempting to re-authenticate.")
                    try:
                        updated_token = self.auth()
                        session.headers["Authorization"] = f"Bearer {updated_token}"
                        # Retry the request with new token
                        resp = session.request(method, url, json=data, params=params, timeout=5)
                    except ValidationError as e:
                        # If authentication fails, bubble up the error
                        _logger.error("Failed to refresh token: %s", str(e))
                        raise

                resp.raise_for_status()
                _logger.info('Successfully responded %s %s', method, url)
                return resp.json()
            except requests.exceptions.RequestException:
                raise ValidationError(_("Fiskaly API request failed, %s", resp.text))
        with session:
            yield request

    def auth(self):
        """Authenticate with Fiskaly and return a bearer token."""
        data = {"api_key": self.api_key, "api_secret": self.api_secret}
        try:
            url = self.base_url + "auth"
            resp = requests.post(url, json=data, timeout=5)
            resp.raise_for_status()
            _logger.info('Successfully authenticated with Fiskaly')
            access_token = resp.json().get('access_token')
            # Update the company record with the new token
            if self.company:
                self.company.l10n_at_fiskaly_access_token = access_token
            return access_token
        except requests.exceptions.RequestException:
            raise ValidationError(_("Fiskaly authentication failed: %s", resp.text))

    def fon_auth(self, bearer_token, data):
        _is_valid, error = fon_schema(data)
        if error:
            raise ValidationError(_("Fiskaly schema validation error, %s", error))
        with self._make_session(bearer_token) as req:
            return req("PUT", endpoint="fon/auth", data=data)

    def setup_scu(self, data, bearer_token):
        _is_valid, error = scu_schema(data)
        if error:
            raise ValidationError(_("Fiskaly schema validation error, %s", error))
        scuid = str(uuid.uuid4())
        with self._make_session(bearer_token) as req:
            req("PUT", endpoint=f'signature-creation-unit/{scuid}', data=data)
            req("PATCH", endpoint=f'signature-creation-unit/{scuid}', data={"state": "INITIALIZED"})
        return scuid

    def setup_cash_reg(self, bearer_token):
        reg_id = str(uuid.uuid4())
        with self._make_session(bearer_token) as req:
            req("PUT", endpoint=f'cash-register/{reg_id}', data={})
            req("PATCH", endpoint=f'cash-register/{reg_id}', data={"state": "REGISTERED"})
            req("PATCH", endpoint=f'cash-register/{reg_id}', data={"state": "INITIALIZED"})
        return reg_id

    def sign_order(self, reg_id, bearer_token, receipt_id, data):
        _is_valid, error = sign_order_schema(data)
        if error:
            raise ValidationError(_("Fiskaly schema validation error, %s", error))
        endpoint = f"cash-register/{reg_id}/receipt/{receipt_id}"
        with self._make_session(bearer_token) as req:
            return req("PUT", endpoint, data=data)

    def get_dep_data(self, bearer_token, cash_regid, start_time, end_time):
        endpoint = f"cash-register/{cash_regid}/export"
        params = {"start_time_signature": start_time, "end_time_signature": end_time} if end_time - start_time > 0 else None
        with self._make_session(bearer_token) as req:
            return req("GET", endpoint, params=params)

    def get_closing_receipt(self, reg_id, receipt_type, offset, bearer_token):
        endpoint = f"cash-register/{reg_id}/receipt"
        params = {
            "receipt_types[]": receipt_type,
            "offset": offset,
            "limit": 1
        }

        with self._make_session(bearer_token) as req:
            return req("GET", endpoint, params=params)


L10N_AT_FISKALY_URL_LIVE = "https://l10n-at-pos.api.odoo.com/api/l10n_at_pos/"
L10N_AT_FISKALY_URL_TEST = "https://l10n-at-pos.test.odoo.com/api/l10n_at_pos/"
IAP_VERSION = 1

iap_schema = object_of({
    'db_uuid': True,
    'company_id': True
})


def fiskaly_iap_rpc(record, endpoint, params):
    _is_valid, error = iap_schema(params)
    if error:
        raise ValidationError(_("Fiskaly schema validation error, %s", error))
    iap_url = L10N_AT_FISKALY_URL_LIVE if not record.l10n_at_pos_test_mode else L10N_AT_FISKALY_URL_TEST
    base_url = iap_url + str(IAP_VERSION)
    return jsonrpc(base_url + endpoint, params=params)
