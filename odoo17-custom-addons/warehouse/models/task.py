from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging
import hashlib
import random
import string
import aiohttp
import asyncio
import json

_logger = logging.getLogger(__name__)

class WarehouseTask(models.Model):
    _name = 'warehouse.task'
    _description = 'Warehouse Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    process_wip_id = fields.Many2one('process.wip', string='Process WIP', required=True)
    name = fields.Char(string="Task Name", required=True)
    assignee = fields.Many2one('res.users', string='Assignee')
    status = fields.Selection([
        ('order_received', 'Order Received'), 
        ('kitting', 'Kitting'), 
        ('checking', 'Checking'), 
        ('packing', 'Packing'),
        ('booking', 'Booking'), 
        ('pick_up_by_courier', 'Pick Up By Courier'), 
        ('done', 'Done')
    ], default='order_received')

    delivery_id = fields.Many2one('stock.picking', related='process_wip_id.delivery_id')

    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)

    shipping_partner_id = fields.Many2one(
        'res.partner',
        related='sale_order_id.partner_shipping_id',
        string="Shipping Address",
        readonly=True,
        store=True  # Important for searching and potentially better performance
    )

    delivery_contact_name = fields.Char(related='shipping_partner_id.name', string="Contact", readonly=True, store=True)
    delivery_phone = fields.Char(related='shipping_partner_id.phone', string="Phone", readonly=True, store=True)
    delivery_email = fields.Char(related='shipping_partner_id.email', string="Email", readonly=True, store=True)
    delivery_street = fields.Char(related='shipping_partner_id.street', string="Street", readonly=True, store=True)
    delivery_street2 = fields.Char(related='shipping_partner_id.street2', string="Street 2", readonly=True, store=True)
    delivery_city = fields.Char(related='shipping_partner_id.city', string="City", readonly=True, store=True)
    delivery_state_id = fields.Many2one(related='shipping_partner_id.state_id', string="State", readonly=True, store=True)
    delivery_zip = fields.Char(related='shipping_partner_id.zip', string="ZIP Code", readonly=True, store=True)
    delivery_country_id = fields.Many2one(related='shipping_partner_id.country_id', string="Country", readonly=True, store=True)

    express_category = fields.Selection([
        ('1' , 'ธรรมดา'),
        ('2' , 'On-Time Delivery'),
        ('4' , 'ราคาพิเศษสำหรับพัสดุขนาดใหญ่'),
        ('6' , 'Happy Return'),
        ('7' , 'Happy Return Bulky'),
    ], default='1', string='ประเภทการจัดส่ง:')

    article_category = fields.Selection([
        ('3' , 'อุปกรณ์ไอที')
    ], default='3', string='ประเภทสินค้า:')

    weight = fields.Float(string='น้ำหนักพัสดุ (กรัม):')
    insured = fields.Selection([
        ( '0', 'ไม่ซื้อ' ),
        ( '1' , 'ซื้อ' )
    ], default='0', string='ซื้อ Flash care หรือไม่:' )
    cod_enabled = fields.Selection([
        ( '0', 'ไม่ใช่' ),
        ( '1' , 'ใช่' )
    ], default='0', string='เป็นพัสดุ COD หรือไม่:')


    # out_trade_no = fields.Char( compute="_compute_flash_express_api_parameters", string="หมายเลข Order", store=True, )
    # dst_name = fields.Char( string="ชื่อผู้รับ", store=True, )
    # dst_phone = fields.Char( string="เบอร์โทรผู้รับ", store=True)
    # dst_province_name = fields.Char( string="จังหวัดของผู้รับ", store=True, )
    # dst_postal_code = fields.Char( string="รหัสไปรษณีย์ของผู้รับ", store=True, )
    # dst_city_name = fields.Char(string="อำเภอของผู้รับ", store=True)
    # dst_detail_address = fields.Char(string="ที่อยู่โดยละเอียดของผู้รับ", store=True)
    out_trade_no = fields.Char(compute="_compute_flash_api_params", string="หมายเลข Order", store=True, readonly=False) # readonly=False if you want it editable or only set by compute
    dst_name = fields.Char(string="ชื่อผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_phone = fields.Char(string="เบอร์โทรผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_province_name = fields.Char(string="จังหวัดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_postal_code = fields.Char(string="รหัสไปรษณีย์ของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_city_name = fields.Char(string="อำเภอของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_detail_address = fields.Char(string="ที่อยู่โดยละเอียดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    
    @api.depends('sale_order_id', 'shipping_partner_id') # Add relevant dependencies
    def _compute_flash_api_params(self):
        for record in self:
            if record.sale_order_id:
                record.out_trade_no = record.sale_order_id.name
            if record.shipping_partner_id:
                record.dst_name = record.shipping_partner_id.name or ''
                # Populate other dst_ fields similarly
                record.dst_phone = record.shipping_partner_id.phone or record.shipping_partner_id.mobile or ''
                record.dst_province_name = record.shipping_partner_id.state_id.name or ''
                record.dst_city_name = record.shipping_partner_id.city or '' # This might need mapping to Flash's district/amphoe
                record.dst_postal_code = record.shipping_partner_id.zip or ''
                record.dst_detail_address = record.shipping_partner_id.street or ''
                if record.shipping_partner_id.street2:
                    record.dst_detail_address += " " + record.shipping_partner_id.street2

    allowed_status_transition_dict = {
            'order_received': ['kitting'],
            'kitting': ['checking'],
            'checking': ['packing'],
            'packing': ['booking'],
            'booking': ['pick_up_by_courier'],
            'pick_up_by_courier': ['done'],
            'done': []
        }
    
    def write(self, vals):
        # Synchronize status changes with process.wip
        if 'status' in vals and not self.env.context.get('from_wip'):
            for record in self:
                if record.process_wip_id:
                    record.process_wip_id.with_context(from_task=True).write({'status': vals['status']})
        return super().write(vals)

    @api.onchange('express_category')
    def _onchange_sale_order_id(self):
        for record in self:
            if record.express_category:
                    record.express_category = '1'  # ตั้งค่าเริ่มต้นที่ถูกต้อง
                    return {'domain': {'expressCategory': "[('id', 'in', ['1'])]"}}
            
    @api.onchange('status')
    def _onchange_status(self):
        for record in self:
            if not record.allowed_status_transition_dict:
                raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี allowed_status_transition_dict.")
            if record.status and record._origin.status:
                allowed_status_transition_dict = record.allowed_status_transition_dict
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.status
                previous_status = record._origin.status
                is_valid_transition = preferred_status in allowed_status_transition_dict.get(previous_status,[])
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.status}.")


    # --- START: Helper Methods for Signature Generation (as per spec) ---
    def _get_system_parameter(self, param_name_suffix, env_prefix=None):
        """
        Fetches a system parameter.
        Example: _get_system_parameter("mch_id", "dev") -> fetches "dev_flash_express.mch_id"
                 _get_system_parameter("src_name") -> fetches "flash_express.src_name" (if env_prefix is None)
        """
        base_param_name = "flash_express_" # Common base for your Flash Express params
        full_param_name = f"{env_prefix+'_' if env_prefix else ''}{base_param_name}{param_name_suffix}"
        
        param_value = self.env['ir.config_parameter'].sudo().get_param(full_param_name)
        if not param_value:
            # You might want to fallback to a non-env specific param if env_prefix was used
            if env_prefix:
                fallback_param_name = f"{base_param_name}{param_name_suffix}"
                param_value = self.env['ir.config_parameter'].sudo().get_param(fallback_param_name)

            if not param_value:
                _logger.warning(f"System parameter '{full_param_name}' (and fallback if applicable) not found.")
                # Depending on how critical, you might return False or raise an error.
                # For this example, let's make it clear for required params later.
        return param_value or False # Return False if not found to be explicitly checked

    def _create_random_string(self, length=32):
        # nonceStr should be a random string.
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for i in range(length))

    def _filter_null_key_value(self, data):
        # "หากค่าพารามิเตอร์ที่เป็นค่าว่างจะไม่นำมาคำนวณในการสร้างลายเซ็น"
        if not data:
            return {}
        return {k: v for k, v in data.items() if v is not None and str(v) != ""}

    def _construct_key_value_string(self, data):
        # "จัดเรียงตามรหัส ASCII ของชื่อพารามิเตอร์ โดยเรียงจากค่าน้อยไปมาก"
        # "รูปแบบ 'key=value'"
        if not data:
            return ""
        
        # Ensure all keys and values are strings for consistent processing
        # string_data = {str(k): str(v) for k, v in data.items()} # Done in _filter_null_key_value if needed for values

        sorted_keys = sorted(data.keys()) # Sorts keys alphabetically (ASCII A-Z)
        key_value_pairs = [f"{key}={data[key]}" for key in sorted_keys]
        string_a = "&".join(key_value_pairs)
        _logger.debug(f"Signature stringA: {string_a}")
        return string_a

    def _construct_presign_string(self, key_value_string, secret_key_value):
        # "stringSignTemp=stringA+'&key=SECRET_KEY'"
        if not secret_key_value: # Crucial check
            _logger.error("Secret key (api_key) is missing for signature generation.")
            raise UserError("Flash Express API Secret Key is not configured.")
        string_sign_temp = f"{key_value_string}&key={secret_key_value}"
        _logger.debug(f"Signature stringSignTemp: {string_sign_temp}")
        return string_sign_temp

    def _sha256_encode(self, text_to_encode):
        # "sign=sha256(stringSignTemp)"
        encoded_text = text_to_encode.encode('utf-8') # Spec: UTF-8
        hashed_text = hashlib.sha256(encoded_text).hexdigest() # Produces lowercase hex
        _logger.debug(f"SHA256 (lowercase): {hashed_text}")
        return hashed_text

    def _transform_string_to_upper_case(self, s):
        # ".toUpperCase()"
        res = s.upper()
        _logger.debug(f"Uppercase: {res}")
        return res
    # --- END: Helper Methods for Signature Generation ---


    async def _call_flash_express_create_order_api(self, session, payload_with_signature):
        """ Makes the actual asynchronous POST request to Flash Express API. """
        
        # Fetch API environment URL from system parameters
        # Example system parameter names:
        # 'flash_express.api_env': can be 'TRAIN' or 'PROD' (or similar)
        # 'flash_express.train_base_url': https://open-api-tra.flashexpress.com
        # 'flash_express.prod_base_url': https://open-api.flashexpress.com
        
        api_env = self._get_system_parameter("api_env") or 'TRAIN' # Default to Training if not set
        base_url = ""
        if api_env.upper() == 'PROD':
            base_url = self._get_system_parameter("prod_base_url")
        else: # Default to training
            base_url = self._get_system_parameter("train_base_url")

        if not base_url:
            _logger.error("Flash Express API base URL is not configured in system parameters.")
            raise UserError("Flash Express API base URL is not configured.")

        api_endpoint = "/open/v3/orders" # For creating orders
        api_url = f"{base_url.rstrip('/')}{api_endpoint}"
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'} # Spec

        _logger.info(f"AIOHTTP: Sending POST request to {api_url}")
        _logger.debug(f"AIOHTTP: Payload for POST (form-urlencoded): {payload_with_signature}")

        response_data = None
        try:
            async with session.post(api_url, data=payload_with_signature, headers=headers, timeout=30) as response:
                response_text = await response.text() # Spec: UTF-8
                _logger.info(f"AIOHTTP: Raw response status: {response.status}")
                _logger.debug(f"AIOHTTP: Raw response body: {response_text}")
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

                try:
                    response_data = json.loads(response_text) # Spec: Response is JSON
                    _logger.info("AIOHTTP: Successfully parsed JSON response.")
                except json.JSONDecodeError:
                    _logger.error(f"AIOHTTP: Failed to decode JSON from response: {response_text}")
                    raise UserError(f"Received an invalid (non-JSON) response from Flash Express: {response_text[:200]}")
                return response_data
        # ... (Keep the robust error handling from the previous example: ClientResponseError, TimeoutError, ClientError, general Exception) ...
        except aiohttp.ClientResponseError as e:
            _logger.error(f"AIOHTTP: HTTP error {e.status} during Flash Express API call: {e.message}. Response: {response_text if 'response_text' in locals() else 'N/A'}")
            error_message_detail = e.message
            if 'response_text' in locals() and response_text:
                try:
                    error_json = json.loads(response_text)
                    error_message_detail = error_json.get('message', e.message) # Check for "การเซ็นลายมือชือล้มเหลว"
                    if "การเซ็นลายมือชือล้มเหลว" in error_message_detail or "sign error" in error_message_detail.lower(): # Example check
                         _logger.error("Flash Express API reported a SIGNATURE VERIFICATION FAILED error.")
                except json.JSONDecodeError: pass
            raise UserError(f"Flash Express API Error ({e.status}): {error_message_detail}")
        except asyncio.TimeoutError:
            _logger.error("AIOHTTP: Request to Flash Express API timed out.")
            raise UserError("The request to Flash Express timed out. Please try again later.")
        except aiohttp.ClientError as e:
            _logger.error(f"AIOHTTP: ClientError during Flash Express API call: {e}")
            raise UserError(f"Could not connect to Flash Express: {e}")
        except Exception as e:
            _logger.error(f"AIOHTTP: An unexpected error occurred during Flash Express API call: {e}", exc_info=True)
            raise UserError(f"An unexpected error occurred while contacting Flash Express: {e}")


    async def _prepare_and_call_flash_express_api_async(self, session):
        self.ensure_one()
        _logger.info(f"Starting Flash Express order creation process for task: {self.name or self.id}")

        # Determine API environment for fetching mch_id and api_key (dev/prod)
        # You could have a system parameter 'flash_express.environment_mode' (e.g., 'dev' or 'prod')
        # to prefix mch_id and api_key parameters.
        # For simplicity, using a single set of params, assuming they are set for the target env.
        # Or use the 'api_env' from system params to decide which key/mchId to use.
        
        # For example, if 'flash_express.api_env' is 'PROD', you might fetch 'prod_flash_express.mch_id'
        # and 'prod_flash_express.api_key'. For 'TRAIN', fetch 'train_flash_express.mch_id', etc.
        # Let's assume _get_system_parameter can handle this logic or you fetch appropriately.
        
        # For the sake of this example, let's assume we get the mchId and api_key for the *current* environment.
        # It's often good practice to have separate mch_id/api_key for TRAIN and PROD environments.
        # e.g., self._get_system_parameter("mch_id", env_prefix="train")
        
        mch_id = self._get_system_parameter("mch_id", "dev") # Example: 'flash_express.mch_id'
        secret_key = self._get_system_parameter("secret_key", "dev") # Example: 'flash_express.secret_key' (this is the API key for signing)

        if not mch_id: raise UserError("Flash Express MCH ID (mchId) is not configured.")
        if not secret_key: raise UserError("Flash Express Secret Key (for signing) is not configured.") # Already checked in _construct_presign_string but good to check early.

        # --- Populate payload_body_for_signing with ALL required parameters for /open/v3/orders ---
        # Ensure all values are of the correct type (string, int) as expected by Flash API
        # and that mandatory fields are present.
        if not self.out_trade_no: raise ValidationError("Order Number (outTradeNo) is required.")
        # ... (add more validations for all required fields like dstName, dstPhone, weight etc.)

        payload_body_for_signing = {
            "mchId" : str(mch_id),
            "nonceStr" : self._create_random_string(32),
            "outTradeNo" : str(self.out_trade_no),
            "expressCategory" : int(self.express_category),
            "srcName" : str(self._get_system_parameter("src_name")), # Configure these in Odoo
            "srcPhone" : str(self._get_system_parameter("src_phone")),
            "srcProvinceName" : str(self._get_system_parameter("src_province_name")),
            "srcCityName" : str(self._get_system_parameter("src_city_name")),
            "srcPostalCode" : str(self._get_system_parameter("src_postal_code")),
            "srcDetailAddress" : str(self._get_system_parameter("src_detail_address")),
            "dstName" : str(self.dst_name),
            "dstPhone" : str(self.dst_phone),
            "dstProvinceName" : str(self.dst_province_name),
            "dstCityName" : str(self.dst_city_name),
            "dstPostalCode" : str(self.dst_postal_code),
            "dstDetailAddress" : str(self.dst_detail_address),
            "articleCategory" : int(self.article_category),
            "weight" : int(self.weight), # In grams
            "insured" : int(self.insured), # 0 or 1
            "codEnabled" : int(self.cod_enabled) # 0 or 1
            # Add other optional fields as needed, ensuring they are included if not empty
            # "codAmount": float(self.cod_amount) if self.cod_enabled == '1' and self.cod_amount > 0 else None,
            # "remark": str(self.remark or ''),
        }
        _logger.debug(f"AIOHTTP: Payload body for signing: {payload_body_for_signing}")
        # _logger.info(f"AIOHTTP: Payload body for signing: {payload_body_for_signing}")

        data_to_sign_filtered = self._filter_null_key_value(payload_body_for_signing.copy()) # Critical: Use a copy for filtering
        key_value_request_string = self._construct_key_value_string(data_to_sign_filtered)
        presign_string = self._construct_presign_string(key_value_request_string, secret_key)
        
        encoded_signature = self._sha256_encode(presign_string)
        final_api_signature = self._transform_string_to_upper_case(encoded_signature)
        
        final_payload_for_post = payload_body_for_signing.copy() # Use original payload body
        final_payload_for_post["sign"] = final_api_signature # Add the sign
        _logger.info(f"AIOHTTP: final_payload_for_post : {final_payload_for_post}")

        return await self._call_flash_express_create_order_api(session, final_payload_for_post)

    def action_create_flash_express_order(self):
        # --- using asyncio.run() or loop.run_until_complete() to call ---
        # --- _prepare_and_call_flash_express_api_async ---
        # --- and then processing the result.                            ---
        self.ensure_one()
        _logger.info(f"User triggered Flash Express order creation for task: {self.name or self.id}")

        async def main_async_wrapper():
            async with aiohttp.ClientSession() as session: # Session created per call
                return await self._prepare_and_call_flash_express_api_async(session)
        try:
            # Simplified asyncio.run() call for this example
            # Proper event loop management in Odoo might require more nuance based on version
            result = asyncio.run(main_async_wrapper())
            _logger.info(f"Flash Express API call completed. Result: {result}")

            if result and isinstance(result, dict):
                if result.get("code") == 1 and result.get("data"):
                    # ... (process successful response as before) ...
                    api_data = result.get("data")
                    pno = api_data.get("pno")
                    self.message_post(body=f"Flash Express order created successfully! PNO: {pno}")
                else:
                    error_message = result.get("message", "API call failed or returned unexpected data.")
                    _logger.error(f"Flash Express API Error: {error_message} - Full Response: {result}")
                    self.message_post(body=f"Flash Express API Error: {error_message}")
            else:
                _logger.error(f"Flash Express API call returned an unexpected result: {result}")
                self.message_post(body=f"Flash Express API call returned an unexpected result.")

        except UserError as ue:
            _logger.error(f"UserError: {ue}")
            self.message_post(body=f"Error: {str(ue)}")
        except ValidationError as ve:
            _logger.error(f"ValidationError: {ve}")
            self.message_post(body=f"Validation Error: {str(ve)}")
        except Exception as e:
            _logger.error(f"Unexpected error: {e}", exc_info=True)
            self.message_post(body=f"An unexpected system error occurred: {str(e)}")
        return True




