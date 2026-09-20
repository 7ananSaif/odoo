# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging

import requests

_logger = logging.getLogger(__name__)


class Wise:
    def __init__(self, company):
        self.url = "https://api.sandbox.transferwise.tech" if company.sudo().wise_environment == 'sandbox' else "https://api.wise.com"
        self.__session = requests.Session()
        self.token = company.sudo().wise_api_key
        self.debug_logger = company._log_external_wise_request
        self.profile_id = company.sudo().wise_profile_identifier

    def __make_api_request(self, method, endpoint, data=None):
        headers = {
            'Content-Type': "application/json",
            'Accept': "application/json",
            'Authorization': f"Bearer {self.token}",
        }

        access_url = self.url + endpoint
        try:
            # Make the API request
            response = self.__session.request(method=method, url=access_url, json=data, headers=headers, timeout=30)
            # Parse the response as JSON
            response_json = response.json()
            # Log the details for debugging purposes
            self.debug_logger(
                f"{access_url} ({method}) {response.status_code}\n\n"
                f"request={json.dumps(data, indent=2)}\n\n"
                f"response={json.dumps(response_json, indent=2)}\n",
                f"_make_api_request ({endpoint})",
            )
            return response_json
        except requests.exceptions.ConnectionError as error:
            _logger.warning('Connection Error: %s with the given URL: %s', error, access_url)
            return {'error': {'description': 'timeout', 'message': "Cannot reach the server. Please try again later."}}
        except requests.exceptions.ReadTimeout as error:
            _logger.warning('Timeout Error: %s with the given URL: %s', error, access_url)
            return {'error': {'description': 'timeout', 'message': "Cannot reach the server. Please try again later."}}
        except json.decoder.JSONDecodeError as error:
            _logger.warning('JSONDecodeError: %s', error)
            return {'error': {'description': 'JSONDecodeError', 'message': str(error)}}
        except Exception as error:  # noqa: BLE001
            _logger.warning('UnknownException: %s', error)
            return {'error': {'description': 'Exception', 'message': str(error)}}

    ########################
    # Error Handling Methods
    ########################
    def has_errors(self, response):
        """ Wise stores all error messages in one of three keys: errors, error, or errorCode """
        return not response or (isinstance(response, dict) and any(key in response for key in ('errors', 'error', 'errorCode')))

    def format_errors(self, error_response):
        if not isinstance(error_response, dict):
            return "An unexpected error occurred while processing your request."

        if "errors" in error_response and isinstance(error_response["errors"], list):
            error_messages = []
            for error in error_response["errors"]:
                if isinstance(error, dict):
                    message = error.get("message", "Unknown validation error")
                    path = error.get("path")
                    arguments = error.get("arguments")

                    # Build the error message
                    if path:
                        error_msg = f"- {path}: {message}"
                    else:
                        error_msg = f"- {message}"

                    # Add arguments information if present and useful
                    if arguments and isinstance(arguments, list):
                        # Filter out the field name if it's already in the path to avoid redundancy
                        filtered_args = [arg for arg in arguments if arg != path]
                        if filtered_args:
                            args_str = ", ".join(str(arg) for arg in filtered_args)
                            error_msg += f" (Value: {args_str})"

                    error_messages.append(error_msg)

            if error_messages:
                return "\n".join(error_messages)
            return "Validation errors occurred but no details were provided."

        if "status" in error_response and "error" in error_response:
            status = error_response.get("status", "Unknown")
            error_type = error_response.get("error", "error")
            message = error_response.get("message", "No additional details provided")
            return f"API Error {status}: {error_type.title()}\n{message}"

        if "error_description" in error_response:
            error_type = error_response.get("error", "error")
            message = error_response.get("error_description", "No additional details provided")
            return f"API Error: {error_type.title()}\n{message}"

        if "type" in error_response and "status" in error_response:
            error_type = error_response.get("type", "Unknown")
            status = error_response.get("status", "Unknown")

            # Build the message
            base_message = f"{error_type} operation {status.lower()}"

            if error_message := error_response.get("errorMessage"):
                return f"{base_message}: {error_message}"
            if error_code := error_response.get("errorCode"):
                # Convert error code to readable format
                readable_code = error_code.replace(".", " ").replace("-", " ").title()
                return f"{base_message}: {readable_code}"
            return base_message
        return "An unexpected API error occurred. Please contact support if the issue persists."

    ########################
    # Profile Methods
    ########################

    def get_profile(self, profile_type="business"):
        """Get user profile from Wise"""
        return self.__make_api_request('GET', '/v1/profiles')

    ########################
    # Quote Methods
    ########################

    def create_quote(self, quote_data):
        """Create quote"""
        profile_id = self.profile_id
        return self.__make_api_request('POST', f'/v3/profiles/{profile_id}/quotes', quote_data)

    ########################
    # Recipient Methods
    ########################

    def create_recipient(self, recipient_data):
        """Create recipient"""
        return self.__make_api_request('POST', '/v1/accounts', recipient_data)

    def get_recipients(self, recipient_id=False):
        """Get recipients"""
        if recipient_id:
            url = f'/v2/accounts/{recipient_id}'
        else:
            url = '/v2/accounts'
        return self.__make_api_request('GET', url)

    ########################
    # Batch Group Methods
    ########################

    def get_batch_group(self, batch_group_id):
        profile_id = self.profile_id
        return self.__make_api_request('GET', f'/v3/profiles/{profile_id}/batch-groups/{batch_group_id}')

    def create_batch_group(self, currency, batch_name):
        """Create batch group"""
        profile_id = self.profile_id

        batch_data = {
            'sourceCurrency': currency,
            'name': batch_name,
        }
        return self.__make_api_request('POST', f'/v3/profiles/{profile_id}/batch-groups', batch_data)

    def create_transfer_in_batch(self, batch_group_id, transfer_data):
        """Create transfer in batch group"""
        profile_id = self.profile_id
        return self.__make_api_request('POST', f'/v3/profiles/{profile_id}/batch-groups/{batch_group_id}/transfers', transfer_data)

    def complete_batch_group(self, batch_group_id, batch_version):
        """Complete batch group"""
        profile_id = self.profile_id

        batch_data = {
            'status': 'COMPLETED',
            'version': batch_version,
        }
        return self.__make_api_request('PATCH', f'/v3/profiles/{profile_id}/batch-groups/{batch_group_id}', batch_data)
