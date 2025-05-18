from odoo import models, fields, api
from odoo.exceptions import ValidationError
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


    out_trade_no = fields.Char( compute="_compute_flash_express_api_parameters", string="หมายเลข Order", store=True, )
    dst_name = fields.Char( string="ชื่อผู้รับ", store=True, )
    dst_phone = fields.Char( string="เบอร์โทรผู้รับ", store=True)
    dst_province_name = fields.Char( string="จังหวัดของผู้รับ", store=True, )
    dst_postal_code = fields.Char( string="รหัสไปรษณีย์ของผู้รับ", store=True, )
    dst_city_name = fields.Char(string="อำเภอของผู้รับ", store=True)
    dst_detail_address = fields.Char(string="ที่อยู่โดยละเอียดของผู้รับ", store=True)
    
    @api.depends('sale_order_id')
    def _compute_flash_express_api_parameters(self):
        for record in self:
            _logger.info(f"record.delivery_phone: {record.delivery_phone}")
            record.out_trade_no = record.sale_order_id.name
            # record.dst_name = record.delivery_contact_name
            # record.dst_phone = record.delivery_phone
            # record.dst_province_name = record.delivery_city
            # record.dst_postal_code = record.delivery_zip

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


    # def action_set_status(self):
    #     """Set status dynamically via button."""
    #     new_status = self.env.context.get('new_status')
    #     if not new_status:
    #         raise ValidationError("No status provided.")
    #     for record in self:
    #         record._validate_and_update_status(new_status)

    # def _validate_and_update_status(self, new_status):
    #     """Private method to validate and update status."""
    #     for record in self:
    #         previous_status = record.status
    #         if not record.allowed_status_transition_dict:
    #             raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี allowed_status_transition_dict.")
            
    #         allowed_status_transition_dict = record.allowed_status_transition_dict
    #         if new_status not in allowed_status_transition_dict.get(previous_status, []):
    #             raise ValidationError(
    #                 f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {new_status}."
    #             )
    #         allowed_status_transition_dict = record.allowed_status_transition_dict
    #         record.status = new_status
    #         if record.process_wip_id:
    #             record.process_wip_id.write({'status': new_status})
    #         else:
    #             raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี process_wip_id.")

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

    # def log_system_parameter(self):
    #     test = self.env['ir.config_parameter'].get_param('dev_mchId')
    #     # api_key = self.env['ir.config_parameter'].sudo().get_param('your_module.api_key')
    #     _logger.info(f"Test: {test}")

    # def test_construct_api_request(self):
    #     request_data = {
    #         "mchId": "AAXXXX",
    #         "nonceStr": self._create_random_string(),
    #         "body": "body_data",
    #         "test_null": ""
    #     }

    #     _logger.info(f"request_data: {request_data}")

    #     filtered_request_data = self._filter_null_key_value(request_data)
    #     _logger.info(f"filtered_request_data: {filtered_request_data}")

    #     key_value_request_string = self._construct_key_value_string(filtered_request_data)
    #     _logger.info(f"key_value_request_string: {key_value_request_string}")

    #     dev_apikey = self._get_api_key("dev")

    #     presign_string = self._construct_presign_string(key_value_request_string, dev_apikey)
    #     _logger.info(f"presign_string: {presign_string}")

    #     encoded_signature = self._sha256_encode(presign_string)
    #     _logger.info(f"encoded_signature: {encoded_signature}")

    #     api_signature = self._transform_string_to_upper_case(encoded_signature)
    #     _logger.info(f"api_signature: {api_signature}")

    def _construct_key_value_string(self, data):
        """
        Constructs a key-value string from a dictionary, sorted in descending order by ASCII key.

        Args:
            data (dict): A dictionary of key-value pairs.

        Returns:
            str: A string in the format "key1=value1&key2=value2&...", sorted DESC by key.
                 Returns an empty string if the input dictionary is empty or None.
        """
        if not data:  # Handle empty or None input
            return ""

        # Filter out keys with None or empty string values *before* sorting.
        filtered_data = {k: v for k, v in data.items() if v is not None and v != ""}

        sorted_keys = sorted(filtered_data.keys())  # Sort keys ASC
        key_value_pairs = [f"{key}={filtered_data[key]}" for key in sorted_keys]
        return "&".join(key_value_pairs)

    def _filter_null_key_value(self, data):
        """
        Filters out key-value pairs from a dictionary where the value is None or an empty string.

        Args:
            data (dict): A dictionary of key-value pairs.

        Returns:
            dict: A new dictionary containing only the key-value pairs with non-null and non-empty string values.
                  Returns an empty dict if input is None or empty.
        """
        if not data:
            return {}
        return {k: v for k, v in data.items() if v is not None and v != ""}

    def _construct_presign_string(self, key_value_string, api_key):
        """
        Constructs the string to be used for generating the signature.

        Args:
            key_value_string (str): The string generated by _construct_key_value_string().
            api_key (str): The API key to append.

        Returns:
            str: The string to be signed (stringA + "&key=API_KEY").  Returns empty string
                 if key_value_string or api_key is empty.
        """
        if not key_value_string or not api_key:
            return ""
        return f"{key_value_string}&key={api_key}"

    def _sha256_encode(self, text):
        """
        Encodes a string using the SHA256 hash function.

        Args:
            text (str): The string to encode.

        Returns:
            str: The SHA256 hash of the input string (in uppercase).
                 Returns an empty string if the input text is empty or None.
        """
        if not text:
            return ""
        encoded_text = text.encode('utf-8')
        hashed_text = hashlib.sha256(encoded_text).hexdigest()
        return hashed_text

    def _create_random_string(self, length=10):
        """
        Generates a random string of a specified length, containing characters and symbols.

        Args:
            length (int, optional): The length of the random string. Defaults to 20.

        Returns:
            str: A random string of the specified length.
        """
        characters = string.ascii_letters + string.digits + string.punctuation
        return ''.join(random.choice(characters) for _ in range(length))
    
    def _get_system_parameter(self, name, env=None):
        """
        Return Odoo system parameter

        Args:
            name (string) name of param
            env (string) prod or dev

        Returns:
            str: an API key of corresponding environment
        """

        if not env:
            return self.env['ir.config_parameter'].get_param(f"{name}")
        else:
            return self.env['ir.config_parameter'].get_param(f"{env}_{name}")

    def _transform_string_to_upper_case(self, str):
        """
        Return uppercase string

        Args:
            str: any string you want to transform to uppercase

        Returns:
            str: uppercase string
        """
        return str.upper()
    

    # Flash APIs 
    async def _create_flash_express_delivery_order(self, session):
        _logger.info("test")
        dev_base_url = "https://open-api-tra.flashexpress.com"
        prod_base_url = "https://open-api.flashexpress.com"

        endpoint = "/open/v3/orders"

        headers = {
            'Content-Type': 'application/json',
            # Add any necessary headers
        }

        payload = {
            "mchId" : self._get_system_parameter("mch_id", "dev"),
            "nonceStr" : self._create_random_string(),
            "outTradeNo" : self.out_trade_no,
            "expressCategory" : int(self.express_category),
            "srcName" : self._get_system_parameter("src_name"),
            "srcPhone" : self._get_system_parameter("src_phone"),
            "srcProvinceName" : self._get_system_parameter("src_province_name"),
            "srcCityName" : self._get_system_parameter("src_city_name"),
            "srcPostalCode" : self._get_system_parameter("src_postal_code"),
            "srcDetailAddress" : self._get_system_parameter("src_detail_address"),
            "dstName" : self.dst_name,
            "dstPhone" : self.dst_phone,
            "dstProvinceName" : self.dst_province_name,
            "dstCityName" : self.dst_city_name,
            "dstPostalCode" : self.dst_postal_code,
            "dstDetailAddress" : self.dst_detail_address,
            "articleCategory" : int(self.article_category),
            "weight" : self.weight,
            "insured" : int(self.insured),
            "codEnabled" : int(self.cod_enabled)
        }

        _logger.info(f"payload: {payload}")

        filtered_request_data = self._filter_null_key_value(payload)
        _logger.info(f"filtered_request_data: {filtered_request_data}")

        key_value_request_string = self._construct_key_value_string(filtered_request_data)
        _logger.info(f"key_value_request_string: {key_value_request_string}")

        dev_api_key = self._get_system_parameter("api_key", "dev")
        _logger.info(f"dev_api_key: {dev_api_key}")

        presign_string = self._construct_presign_string(key_value_request_string, dev_api_key)
        _logger.info(f"presign_string: {presign_string}")

        encoded_signature = self._sha256_encode(presign_string)
        _logger.info(f"encoded_signature: {encoded_signature}")

        api_signature = self._transform_string_to_upper_case(encoded_signature)
        _logger.info(f"api_signature: {api_signature}")

        payload["sign"] = api_signature
        _logger.info(f"final payload: {payload}")

        url="https://open-api-tra.flashexpress.com/open/v3/orders"
        try:
            async with session.post(url, data=json.dumps(payload), headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                _logger.info(f"Async POST request successful. Response: {data}")
                # Process the response data asynchronously
                return data
        except aiohttp.ClientError as e:
            _logger.error(f"Async POST request failed: {e}")
            return None
        except json.JSONDecodeError:
            _logger.error("Error decoding JSON response.")
            return None
        except Exception as e:
            _logger.error(f"An unexpected error occurred during async request: {e}")
            return None

    def trigger_async_post(self):
        async def main():
            async with aiohttp.ClientSession() as session:
                result = await self._create_flash_express_delivery_order(session)
                _logger.info(f"Async task completed with result: {result}")

        asyncio.run(main())




