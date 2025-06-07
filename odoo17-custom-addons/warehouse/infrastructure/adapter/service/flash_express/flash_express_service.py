import requests
import json
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class FlashExpressService:
    def __init__(self, flash_helper):
        """
        :param flash_helper: An instance of FlashExpressHelper
        """
        self.flash_helper = flash_helper

    def _make_api_call(self, api_url, signed_payload, expected_content_type='json', timeout=60):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'} # Flash spec
        if expected_content_type == 'pdf':
            headers['Accept'] = 'application/pdf, */*'
        else: # Default to JSON
            headers['Accept'] = 'application/json'

        _logger.info(f"REQUESTS: Sending POST to {api_url}")
        _logger.debug(f"REQUESTS: Payload (form-urlencoded): {signed_payload}")
        
        try:
            response = requests.post(api_url, data=signed_payload, headers=headers, timeout=timeout)
            _logger.info(f"REQUESTS: Response Status: {response.status_code}")

            if expected_content_type == 'pdf':
                if response.ok: # Status code 2xx
                    if response.content:
                        return response.content # Return raw bytes
                    else:
                        _logger.warning(f"Received empty PDF response from {api_url}")
                        raise UserError("Received an empty PDF response from Flash Express.")
                else: # PDF request failed
                    error_text = response.text
                    _logger.error(f"REQUESTS PDF Error {response.status_code}: {error_text[:500]}")
                    response.raise_for_status() # Raise HTTPError to be caught below

            # For JSON responses
            response_text = response.text
            _logger.debug(f"REQUESTS JSON Response Body: {response_text}")
            response.raise_for_status() # Raise HTTPError for 4xx/5xx

            try:
                response_data = response.json()
                _logger.info("REQUESTS: Successfully parsed JSON response.")
                return response_data
            except json.JSONDecodeError:
                _logger.error(f"REQUESTS: Failed to decode JSON: {response_text}")
                raise UserError(f"Invalid JSON response from Flash Express: {response_text[:200]}")

        except requests.exceptions.HTTPError as e:
            err_resp = e.response
            err_text = err_resp.text if err_resp is not None else "No response body"
            status_code = err_resp.status_code if err_resp is not None else "N/A"
            _logger.error(f"REQUESTS HTTP Error {status_code}: {e}. Response: {err_text[:500]}")
            
            msg_detail = str(e)
            try: # Try to parse error message from Flash
                err_json = json.loads(err_text)
                msg_detail = err_json.get('message', str(e))
                if "การเซ็นลายมือชือล้มเหลว" in msg_detail or "sign error" in msg_detail.lower():
                    _logger.error("Flash Express reported: SIGNATURE VERIFICATION FAILED.")
            except (json.JSONDecodeError, TypeError): pass
            raise UserError(f"Flash API Error ({status_code}): {msg_detail}")
        except requests.exceptions.Timeout:
            _logger.error(f"REQUESTS: Timeout calling {api_url}")
            raise UserError("Request to Flash Express timed out. Please try again.")
        except requests.exceptions.RequestException as e: # Other issues (DNS, Connection refused)
            _logger.error(f"REQUESTS: RequestException for {api_url}: {e}")
            raise UserError(f"Connection error with Flash Express: {e}")
        except Exception as e:
            _logger.error(f"REQUESTS: Unexpected error for {api_url}: {e}", exc_info=True)
            raise UserError(f"Unexpected error contacting Flash Express: {e}")

    def create_order(self, task_record):
        if task_record.delivery_order_id:
            _logger.warning(f"Task {task_record.name}: Delivery order already exists ({task_record.delivery_order_id}). Skipping.")
            return {"code": 0, "message": "Delivery order ID already exists."} # Existing behavior
        if task_record.status != 'packing':
            raise UserError("Flash Express order can only be created when task status is 'packing'.")

        api_url, mch_id, secret_key = self.flash_helper.get_api_credentials_and_url({'key': "create_order"})

        # Essential payload fields (mchId and nonceStr added by helper)
        payload_body = {
            "outTradeNo" : str(task_record.out_trade_no),
            "expressCategory" : int(task_record.express_category), # e.g. 1
            "srcName" : str(self.flash_helper.get_system_parameter("src_name")),
            "srcPhone" : str(self.flash_helper.get_system_parameter("src_phone")),
            "srcProvinceName" : str(self.flash_helper.get_system_parameter("src_province_name")),
            "srcCityName" : str(self.flash_helper.get_system_parameter("src_city_name")),
            "srcPostalCode" : str(self.flash_helper.get_system_parameter("src_postal_code")),
            "srcDetailAddress" : str(self.flash_helper.get_system_parameter("src_detail_address")),
            "dstName" : str(task_record.dst_name),
            "dstPhone" : str(task_record.dst_phone),
            "dstProvinceName" : str(task_record.dst_province_name), # Make sure these map correctly
            "dstCityName" : str(task_record.dst_city_name),         # Amphoe/District
            "dstPostalCode" : str(task_record.dst_postal_code),
            "dstDetailAddress" : str(task_record.dst_detail_address),
            "articleCategory" : int(task_record.article_category), # e.g. 3
            "weight" : int(task_record.weight), # Grams
            "insured" : int(task_record.insured), # 0 or 1
            "codEnabled" : int(task_record.cod_enabled) # 0 or 1
            # Add "codAmount" if codEnabled == 1:
            # "codAmount": float(task_record.sale_order_id.amount_total) if task_record.cod_enabled == '1' else None,
            # Add other optional fields like "remark", dimensions ("length", "width", "height") if needed
        }
        # Example for codAmount if needed:
        if task_record.cod_enabled == '1':
             # Ensure you have a field for COD amount or derive it, e.g., from sale_order_id
             cod_amount = task_record.sale_order_id.amount_total
             if cod_amount > 0:
                 payload_body["codAmount"] = float(cod_amount) # Ensure it's a float
             else: # COD enabled but amount is zero or invalid
                 _logger.warning("COD is enabled but amount is 0 for order %s. codAmount will not be sent.", task_record.out_trade_no)
                 # Flash API might require codAmount if codEnabled is 1. Adjust logic as per API spec.


        if not task_record.out_trade_no: raise UserError("Order Number (outTradeNo) is required.")
        # Add more field validations as necessary

        signed_payload = self.flash_helper.generate_signed_payload(payload_body, mch_id, secret_key)
        return self._make_api_call(api_url, signed_payload, expected_content_type='json')

    def print_label(self, task_record):
        if not task_record.delivery_order_id:
            raise UserError("Flash Express PNO (tracking number) is not set. Cannot print label.")
        
        pno = task_record.delivery_order_id
        api_url, mch_id, secret_key = self.flash_helper.get_api_credentials_and_url({
            'key': "print_label", 'pno_for_path': pno
        })
        
        # For print label, the body to sign only contains mchId and nonceStr
        # The PNO is part of the URL path and not in the signed body.
        payload_body_for_signing = {} 
        signed_payload = self.flash_helper.generate_signed_payload(payload_body_for_signing, mch_id, secret_key)
        
        return self._make_api_call(api_url, signed_payload, expected_content_type='pdf', timeout=90)
    
    def notify_courier_to_pick_up(self, pickup_request_record):
        if not pickup_request_record.task_count:
            _logger.warning(f"Pickup_Request {pickup_request_record.name}: Not included with any tasks. Please add tasks to Pickup Request.")
            return {"code": 0, "message": "Tasks is empty."}
        if pickup_request_record.status != 'draft':
            raise UserError("Flash Express courier can be called only when Pickup Request status is 'draft'.")

        api_url, mch_id, secret_key = self.flash_helper.get_api_credentials_and_url({'key': "notify"})
        
        payload_body = {
            "srcName" : str(self.flash_helper.get_system_parameter("src_name")),
            "srcPhone" : str(self.flash_helper.get_system_parameter("src_phone")),
            "srcProvinceName" : str(self.flash_helper.get_system_parameter("src_province_name")),
            "srcCityName" : str(self.flash_helper.get_system_parameter("src_city_name")),
            "srcPostalCode" : str(self.flash_helper.get_system_parameter("src_postal_code")),
            "srcDetailAddress" : str(self.flash_helper.get_system_parameter("src_detail_address")),
            "estimateParcelNumber" : int(pickup_request_record.task_count)
            # 'remark' : "" => optional field
        }
    
        signed_payload = self.flash_helper.generate_signed_payload(payload_body, mch_id, secret_key)
        return self._make_api_call(api_url, signed_payload, expected_content_type='json')

    def check_status(self, task_record):
        if not task_record.delivery_order_id:
            raise UserError("Flash Express PNO (tracking number) is not set. Cannot check status.")

        pno = task_record.delivery_order_id
        api_url, mch_id, secret_key = self.flash_helper.get_api_credentials_and_url({
            'key': "check_status", 'pno_for_path': pno
        })

        # For check status, the body to sign only contains mchId and nonceStr.
        # The PNO is part of the URL path.
        payload_body_for_signing = {}
        signed_payload = self.flash_helper.generate_signed_payload(payload_body_for_signing, mch_id, secret_key)
        
        return self._make_api_call(api_url, signed_payload, expected_content_type='json')