import logging
import hashlib
import random
import string
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class FlashExpressHelper:
    def __init__(self, env):
        self.env = env

    def get_system_parameter(self, param_name_suffix, env_prefix=None):
        base_param_name = "flash_express_"
        # Construct name like 'dev_flash_express_mch_id' or 'flash_express_api_env'
        full_param_name = f"{env_prefix+'_' if env_prefix else ''}{base_param_name}{param_name_suffix}"
        
        param_value = self.env['ir.config_parameter'].sudo().get_param(full_param_name)
        if not param_value:
            if env_prefix: # Fallback if environment-specific param not found
                fallback_param_name = f"{base_param_name}{param_name_suffix}"
                param_value = self.env['ir.config_parameter'].sudo().get_param(fallback_param_name)
            if not param_value:
                _logger.warning(f"System parameter '{full_param_name}' (and fallback if applicable) not found.")
        return param_value or False

    def create_random_string(self, length=32):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def filter_null_key_value(self, data):
        if not data: return {}
        return {k: v for k, v in data.items() if v is not None and str(v) != ""}

    def construct_key_value_string(self, data):
        if not data: return ""
        sorted_keys = sorted(data.keys())
        key_value_pairs = [f"{key}={data[key]}" for key in sorted_keys]
        string_a = "&".join(key_value_pairs)
        _logger.debug(f"Signature stringA: {string_a}")
        return string_a

    def construct_presign_string(self, key_value_string, secret_key_value):
        if not secret_key_value:
            _logger.error("Secret key (api_key) is missing for signature generation.")
            raise UserError("Flash Express API Secret Key is not configured.")
        string_sign_temp = f"{key_value_string}&key={secret_key_value}"
        _logger.debug(f"Signature stringSignTemp: {string_sign_temp}")
        return string_sign_temp

    def sha256_encode(self, text_to_encode):
        encoded_text = text_to_encode.encode('utf-8')
        hashed_text = hashlib.sha256(encoded_text).hexdigest()
        _logger.debug(f"SHA256 (lowercase): {hashed_text}")
        return hashed_text

    def transform_string_to_upper_case(self, s):
        res = s.upper()
        _logger.debug(f"Uppercase: {res}")
        return res

    def get_api_credentials_and_url(self, endpoint_config):
        """
        Fetches API base URL, merchant ID, and secret key based on environment.
        :param endpoint_config: dict containing {'key': 'create_order', 'pno_for_path': 'optional_pno'}
        :return: tuple (api_url, mch_id, secret_key)
        """
        api_env = self.get_system_parameter("api_env") or 'TRAIN'
        # Use 'prod' prefix for production credentials, 'dev' for others (e.g., TRAIN)
        credential_env_prefix = 'prod' if api_env.upper() == 'PROD' else 'dev'
        
        base_url_param_key = f"{api_env.lower()}_base_url" # e.g., train_base_url
        base_url = self.get_system_parameter(base_url_param_key)

        if not base_url:
            msg = f"Flash Express API base URL for env '{api_env}' ('{base_url_param_key}') not configured."
            _logger.error(msg)
            raise UserError(msg)

        mch_id = self.get_system_parameter("mch_id", credential_env_prefix)
        secret_key = self.get_system_parameter("secret_key", credential_env_prefix)

        if not mch_id: raise UserError(f"Flash Express MCH ID for env '{credential_env_prefix}' not configured.")
        if not secret_key: raise UserError(f"Flash Express Secret Key for env '{credential_env_prefix}' not configured.")

        # Determine endpoint path
        path = ""
        endpoint_key = endpoint_config.get('key')
        if endpoint_key == "create_order":
            path = "/open/v3/orders"
        elif endpoint_key == "print_label":
            pno = endpoint_config.get('pno_for_path')
            if not pno: raise UserError("PNO is required for print label endpoint.")
            path = f"/open/v1/orders/{pno}/small/pre_print"
        elif endpoint_key == "notify":
            path = "/open/v1/notify"
        elif endpoint_key == "cancel_notification":
            path = "/open/v1/notify/{id}/cancel"
        elif endpoint_key == "check_status":
            pno = endpoint_config.get('pno_for_path')
            if not pno: raise UserError("PNO is required for check status endpoint.")
            path = f"/open/v1/orders/{pno}/routes"
        else:
            raise UserError(f"Unknown API endpoint key: {endpoint_key}")
            
        api_url = f"{base_url.rstrip('/')}{path}"
        return api_url, mch_id, secret_key

    def generate_signed_payload(self, payload_body_for_signing, mch_id, secret_key):
        """
        Generates nonceStr, adds mchId, creates signature, and returns the full payload for POST.
        payload_body_for_signing should contain only the specific data for the endpoint,
        mchId and nonceStr will be added by this method.
        """
        # Add mchId and nonceStr to the parameters that will be signed
        params_to_sign = {
            "mchId": str(mch_id),
            "nonceStr": self.create_random_string(32),
            **(payload_body_for_signing if payload_body_for_signing else {}) # Merge endpoint-specific data using tuple unpacking operator same as js spread operator in object.
        }
        
        data_to_sign_filtered = self.filter_null_key_value(params_to_sign.copy()) # Sign non-null values
        key_value_string = self.construct_key_value_string(data_to_sign_filtered)
        presign_string = self.construct_presign_string(key_value_string, secret_key)
        encoded_signature = self.sha256_encode(presign_string)
        final_api_signature = self.transform_string_to_upper_case(encoded_signature)
        
        # The final payload sent to the API includes all signed parameters + the signature
        final_post_payload = params_to_sign.copy()
        final_post_payload["sign"] = final_api_signature
        return final_post_payload

    