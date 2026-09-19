import base64
import hashlib
import io
import logging
import requests
import secrets
import string
import uuid
import zipfile

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import Encoding
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from json.decoder import JSONDecodeError
from urllib.parse import urlencode

from odoo import fields, models, modules, tools
from odoo.exceptions import RedirectWarning, UserError
from odoo.http import request
from odoo.tools import LazyTranslate

_logger = logging.getLogger(__name__)

try:
    import jwt
    from jwt.exceptions import ImmatureSignatureError, InvalidSignatureError
except ImportError:
    jwt = None
    _logger.error("The PyJWT module is not installed, Intervat might not work as expected.")

ALLOWED_CHARS = string.ascii_letters + string.digits + "-._~"
BASE_URL = {
    'test': "https://wsapi-a.minfin.be",
    'prod': "https://wsapi.minfin.fgov.be",
    'disabled': "",
}
TOKEN_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/access_token",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/access_token",
    'disabled': "",
}
JWKS_ENDPOINT = {
    'test': "https://fediamapi-a.minfin.be/sso/oauth2/connect/jwk_uri",
    'prod': "https://fediamapi.minfin.fgov.be/sso/oauth2/connect/jwk_uri",
    'disabled': "",
}
IAP_ENDPOINT = {
    'test': "https://l10n-be-intervat.test.odoo.com/api/l10n_be_intervat/1",
    'prod': "https://l10n-be-intervat.api.odoo.com/api/l10n_be_intervat/1",
    'disabled': "",
}

_intervat_logger = logging.getLogger(__name__ + '.l10n_be_intervat')
_lt = LazyTranslate(__name__)

IAP_ERROR_MESSAGE = {
    'error_subscription': _lt("An error has occurred when trying to verify your subscription."),
    'dbuuid_not_exist': _lt("Your database UUID does not exist."),
    'not_enterprise': _lt("You do not have an Odoo Enterprise subscription."),
    'not_prod_env': _lt("Your database is not used for a production environment."),
    'not_active_db': _lt("Your database is not yet activated."),
    'limit_call_reached': _lt("You reached the call limit. Please try again in a moment."),
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_be_intervat_refresh_token = fields.Char(groups='account.group_account_user')
    l10n_be_intervat_access_token = fields.Char(groups='account.group_account_user')
    l10n_be_intervat_code_challenge = fields.Char(groups='account.group_account_user')
    l10n_be_intervat_code_verifier = fields.Char(groups='account.group_account_user')
    l10n_be_intervat_client_id = fields.Char(string="Intervat Client ID", groups='account.group_account_user')
    l10n_be_intervat_private_key = fields.Many2one(
        string="Intervat Private Key",
        comodel_name='certificate.key',
        domain=[('public', '=', False)],
        groups='account.group_account_user',
    )
    l10n_be_intervat_certificate_id = fields.Many2one(
        string="Intervat JWT Certificate",
        comodel_name='certificate.certificate',
        domain=[('is_valid', '=', True)],
        groups='account.group_account_user',
    )
    l10n_be_intervat_mode = fields.Selection(
        selection=[
            ('prod', "Production"),
            ('test', "Test"),
            ('disabled', "Disabled"),
        ],
        default="prod",
        string="Intervat Server Mode",
        help="""
            - Production: Connected to the Intervat API in production mode
            - Test: Connected to the Intervat API in test mode
            - Disabled: Disconnected from the Intervat server
        """,
        groups='account.group_account_user',
        required=True,
    )
    l10n_be_intervat_last_call_date = fields.Datetime(groups='account.group_account_user')

    ########################################
    # Tokens & Certificates                #
    ########################################

    def _l10n_be_generate_private_key_and_certificate(self):
        """ Generate a new certificate and a new private key to be used for api calls.
            The certificate follows the x509 standard.
            This certificate is supposed to be stored in the jwks url, to be retrieved by the government apis
            to check the jwt signature.
        """
        # We only generate a new certificate and a new key if nothing is set on the company yet.
        # Otherwise, we're using the same.
        if not self.l10n_be_intervat_private_key or not self.l10n_be_intervat_certificate_id.is_valid:
            if self.l10n_be_intervat_certificate_id:
                self.l10n_be_intervat_certificate_id.unlink()
                self.l10n_be_intervat_private_key.unlink()
            self.l10n_be_intervat_private_key = self.env['certificate.key'].sudo()._generate_rsa_private_key(
                company=self,
                name='intervat_private_key_%s' % fields.Datetime.now().strftime("%Y%m%d_%H%M%S"),
            )
            subject = x509.Name([
                x509.NameAttribute(x509.oid.NameOID.COUNTRY_NAME, self.country_code),
                x509.NameAttribute(x509.oid.NameOID.ORGANIZATION_NAME, self.name),
                x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, self.website or 'N/A'),
                x509.NameAttribute(x509.oid.NameOID.LOCALITY_NAME, self.city or 'N/A'),
            ])
            private_key = serialization.load_pem_private_key(
                base64.b64decode(self.l10n_be_intervat_private_key.pem_key),
                None
            )
            certificate = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now()
            ).not_valid_after(
                datetime.now() + timedelta(days=365)
            ).sign(
                private_key=private_key,
                algorithm=hashes.SHA256(),
            )
            self.l10n_be_intervat_certificate_id = self.env['certificate.certificate'].create([{
                'name': f"Intervat Certificate: {self.name}",
                'content': base64.b64encode(certificate.public_bytes(encoding=serialization.Encoding.PEM)),
                'private_key_id': self.l10n_be_intervat_private_key.id,
                'company_id': self.id,
            }])

        self.l10n_be_intervat_code_verifier = ''.join([secrets.choice(ALLOWED_CHARS) for _ in range(60)])
        sha256_hash = hashlib.sha256(self.l10n_be_intervat_code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(sha256_hash).rstrip(b'=').decode()
        self.l10n_be_intervat_code_challenge = code_challenge

        jwk = self._l10n_be_generate_jwk()
        params = {
            **jwk,
            'company_token': hashlib.sha256(self.l10n_be_intervat_certificate_id.l10n_be_intervat_jwk_token.encode()).hexdigest(),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'root_url': request.httprequest.root_url,
        }
        response = requests.post(
            url=f"{IAP_ENDPOINT[self.l10n_be_intervat_mode]}/register_jwk",
            params=params,
        )
        if not response.ok:
            if error_message := IAP_ERROR_MESSAGE.get(response.text):
                raise UserError(error_message)
            raise UserError(self.env._("Error while generating the certificate."))

    def _l10n_be_generate_jwt(self):
        """ Generate a new jwt to send to the government apis. This jwt is signed with the x509 certificate private key. """
        if jwt is None:
            _logger.error("The library 'PyJWT' is missing, cannot generate a new jwt.")
            return ''

        private_key = serialization.load_pem_private_key(
            base64.b64decode(self.l10n_be_intervat_private_key.pem_key),
            None
        )
        expiration_time = datetime.now(timezone.utc) + timedelta(minutes=1)
        expiration_timestamp = int(expiration_time.timestamp())
        header, payload = {
            'alg': 'RS256',
            'typ': 'JWT',
            'kid': self.l10n_be_intervat_certificate_id.l10n_be_intervat_jwk_kid,
        }, {
            'iss': 'odoo',
            'sub': 'odoo',
            'aud': TOKEN_ENDPOINT[self.l10n_be_intervat_mode],
            'exp': expiration_timestamp,
            'jti': secrets.token_hex(16),
        }
        return jwt.encode(payload, private_key, headers=header, algorithm=header['alg'])

    def _l10n_be_generate_jwk(self):
        """ Generate one jwk to be sent to IAP to be stored in the jwks url. """
        def to_base64url(b64_bytes):
            b64_str = b64_bytes.replace(b'\n', b'').replace(b'\r', b'')
            raw = base64.b64decode(b64_str)
            return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()

        pem_certificate = base64.b64decode(self.l10n_be_intervat_certificate_id.pem_certificate)
        cert = x509.load_pem_x509_certificate(pem_certificate, default_backend())
        cert_der = cert.public_bytes(encoding=Encoding.DER)
        x5c_value = self.l10n_be_intervat_certificate_id._get_der_certificate_bytes().decode()
        sha1_thumbprint = hashlib.sha1(cert_der).digest()
        x5t_value = base64.urlsafe_b64encode(sha1_thumbprint)
        e, n = self.l10n_be_intervat_certificate_id._get_public_key_numbers_bytes()

        return {
            "key_type": 'RSA',
            "key_id": self.l10n_be_intervat_certificate_id.l10n_be_intervat_jwk_kid,
            "key_use": 'sig',
            "certificate_thumbprint": x5t_value.decode().rstrip('='),
            "certificate_chain": x5c_value.rstrip('\n'),
            "key_modulus": to_base64url(n),
            "key_exponent": to_base64url(e),
        }

    def _l10n_be_refresh_token(self):
        """ Retrieve new tokens to call the apis. Access tokens are one shot tokens, so we have
            to get a new one before each call.

            :return: True if tokens has been generated, else False.
        """
        if not self._l10n_be_intervat_is_authentication_valid():
            return False

        response = requests.post(
            url=TOKEN_ENDPOINT[self.l10n_be_intervat_mode],
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.l10n_be_intervat_refresh_token,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': self._l10n_be_generate_jwt(),
            },
            headers={
                'accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        response_json, error = self._l10n_be_get_error_from_response(response)

        if error:
            raise UserError(error['error_message'])

        self._l10n_be_verify_id_token_signature(response_json['id_token'])
        self.l10n_be_intervat_access_token = response_json['access_token']
        self.l10n_be_intervat_refresh_token = response_json['refresh_token']

        # In case an error occurs, we need to commit the tokens in the db as they're about to be used in the calling request
        if not tools.config['test_enable'] and not modules.module.current_test:
            self.env.cr.commit()

        return True

    def _l10n_be_verify_id_token_signature(self, id_token):
        """ Check the signature of the jwt sent by the government. """
        if jwt is None:
            raise UserError(self.env._("The library 'PyJWT' is missing, cannot verify the jwt signature."))

        jwt_header = jwt.get_unverified_header(id_token)
        kid = jwt_header.get('kid')
        response = requests.get(
            url=JWKS_ENDPOINT[self.l10n_be_intervat_mode],
        )
        response_json, error = self._l10n_be_get_error_from_response(response)
        if error:
            raise UserError(error['error_message'])
        jwk = next((jwk for jwk in response_json['keys'] if jwk.get('kid') == kid), None)
        if not jwk:
            raise UserError(self.env._("Impossible to check the response signature."))

        cert = x509.load_der_x509_certificate(base64.b64decode(jwk['x5c'][0]), default_backend())
        public_key = cert.public_key()
        try:
            decoded_jwt = jwt.decode(
                jwt=id_token,
                algorithms='RS256',
                key=public_key,
                audience='odoo',
            )
        except InvalidSignatureError:
            raise UserError(self.env._("The signature of the JWT is not matching."))

        except ImmatureSignatureError:
            raise UserError(self.env._("The token is not valid yet."))

        return decoded_jwt

    ########################################
    # Actions                              #
    ########################################

    def _l10n_be_intervat_authentication_action(self, return_id, request_type):
        self._l10n_be_intervat_check_activated()
        self._l10n_be_generate_private_key_and_certificate()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/l10n_be_intervat/authorize/{self.id}/{return_id}/{request_type}',
            'target': 'self',
        }

    ########################################
    # Api's call                           #
    ########################################

    def _l10n_be_fetch_document_from_myminfin(self, document_uuid):
        """ Fetch one document from the MyMinFin api. Documents could either be xml or pdf and represent
            a declaration. Documents are only available the day after the declaration.

            :param document_uuid: UUID of the document to fetch. This id is sent back when submitting
                                  a declaration.

            :return: Response from MyMinFin api with file content. Return -1 if refresh token is expired.
        """
        url = f"{BASE_URL[self.l10n_be_intervat_mode]}/FineAPI/Generic/OAU/v2/documents/{document_uuid}/content"
        auth_url_params = urlencode({
            'ownerType': 'CBE',
            'ownerIdentifier': self.company_registry,
        })
        if not self._l10n_be_refresh_token():
            return None

        url += f"?{auth_url_params}"

        response = requests.get(
            url=url,
            headers={
                'Authorization': f'Bearer {self.l10n_be_intervat_access_token}',
                'Minfin-Ws-Correlation': f"{uuid.uuid4()}",
            },
        )
        response_content, error = self._l10n_be_get_error_from_response(response, parse_json=False)
        if error:
            raise UserError(error['error_message'])
        return response_content

    def _l10n_be_post_vat_declaration(self, xml_content: bytes, file_name: str):
        """ Submit a vat return xml to the Intervat api. The format of the file is a zip file with only
            one xml file in it as it's a technical requirement asked by the api.

            :param xml_content: Content of the xml file from the tax report.
            :param file_name: File name of the xml file to be added in the zip file.

            :return: Response from api with pdf and xml UUID, which can be used to fetch related documents from
                     MyMinFin API. Return None if refresh token is expired.
        """
        url = f"{BASE_URL[self.l10n_be_intervat_mode]}/Intervat/api/OAU/v1/declaration/vat/{self.company_registry}"
        if not self._l10n_be_refresh_token():
            return None

        with io.BytesIO() as buffer:
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipfile_obj:
                zipfile_obj.writestr(file_name, xml_content)

            response = requests.post(
                url=url,
                data=buffer.getvalue(),
                headers={
                    'Authorization': f'Bearer {self.l10n_be_intervat_access_token}',
                    'Content-Type': 'application/zip',
                }
            )
            response_json, error = self._l10n_be_get_error_from_response(response)
            if error:
                raise UserError(error['error_message'])
            return {
                'pdfReference': response_json['pdfReference'],
                'xmlReference': response_json['xmlReference'],
            }

    def _l10n_be_get_error_from_response(self, response, parse_json=True):
        """ Check if the response from Intervat is valid or not.

            :param response: Response from Intervat
            :param parse_json: Whenever we want to parse the response from Intervat or not. We don't want
                               to parse the response if the request is meant to fetch a document.

            :return: tuple(formatted response, errors).
        """
        try:
            formatted_response = response.json() if parse_json else response.content
            response.raise_for_status()
            return formatted_response, {}

        except JSONDecodeError as error:
            return {}, {'error_message': error.msg, 'error_code': response.status_code}

        except requests.exceptions.HTTPError as error:
            response_json = response.json()
            if 'businessrules' in response_json:
                error_message = ""
                for rule in response_json['businessrules']:
                    lang_prefix = self.env.lang[:2] if self.env.lang[:2] in ('nl', 'fr', 'de', 'en') else 'en'
                    error_message += f"{rule['descriptions'][lang_prefix]}\n"
                return {}, {'error_message': error_message, 'error_code': response.status_code}

            if 'detail' in response_json:
                error_message = response_json['detail']
                if not parse_json and response.status_code == 403:
                    error_message += "\n" + self.env._("If you just submitted your declaration, you might need to wait until tomorrow to fetch the documents. You can still retrieve them from the Intervat Portal.")
                return {}, {'error_message': error_message, 'error_code': response.status_code}

            return {}, {'error_message': error.response.content.decode(), 'error_code': response.status_code}

    ########################################
    # Utils                                #
    ########################################

    def _l10n_be_intervat_is_authentication_valid(self):
        return self.l10n_be_intervat_access_token \
            and fields.Datetime.now() - relativedelta(hours=4) < self.l10n_be_intervat_last_call_date

    def _l10n_be_intervat_check_activated(self):
        if self.l10n_be_intervat_mode == 'disabled':
            raise RedirectWarning(
                self.env._('Intervat is not activated. You can activate it in the settings.'),
                'account.action_account_config',
                self.env._('Set Intervat mode'),
            )
