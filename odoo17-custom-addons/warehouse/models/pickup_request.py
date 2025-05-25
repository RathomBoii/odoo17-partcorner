from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT # For formatting datetime if needed, though from_timestamp handles it

import aiohttp
import asyncio
import json
import logging
import hashlib # For SHA256
import random # For nonceStr
import string # For nonceStr

_logger = logging.getLogger(__name__)

class WarehousePickupRequest(models.Model):
    _name = 'warehouse.pickup_request'
    _description = 'Warehouse Courier Pickup Request'
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string="Request Name/ID", 
        required=True, 
        copy=False, 
        readonly=True, 
        index=True, 
        default=lambda self: _('New')
    )
    request_date = fields.Datetime(
        string="Request Date", 
        required=True, 
        default=fields.Datetime.now, 
        index=True,
        readonly=True, states={'draft': [('readonly', False)]}
    )
    user_id = fields.Many2one(
        'res.users', 
        string='Requested By', 
        default=lambda self: self.env.user, 
        readonly=True,
        copy=False
    )

    task_ids = fields.One2many(
        comodel_name='warehouse.task',  # The technical name of your task model
        inverse_name='pickup_request_id', # The name of the Many2one field on the warehouse.task model
        string='Associated Tasks'
    )


    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Courier Requested (API Call Made)'), 
        # ('confirmed_by_flash', 'Pickup Confirmed by Flash'),
        # ('failed', 'Request Failed'),
    ], string='Status', default='draft', readonly=True, copy=False, tracking=True)

    # Input parameters for the "Notify Courier" API
    flash_notify_estimate_parcel_number = fields.Integer(
        string="Est. Parcel Count for Pickup",
        compute='_compute_flash_notify_estimate_parcel_number',
        inverse='_inverse_flash_notify_estimate_parcel_number',
        store=True,
        readonly=False,
        default=1,
        tracking=True,
        help="Computed based on tasks in 'Booking' status. Can be manually overridden in Draft state."
    )
    flash_notify_estimate_manual_override = fields.Boolean(
        string="Manual Estimate Override", 
        default=False, 
        copy=False
    )
    flash_pickup_remark = fields.Char(
        string="Remark for Courier",
        tracking=True,
        states={'draft': [('readonly', False)]}
    )

    # Response fields from the "Notify Courier" API
    flash_ticket_pickup_id = fields.Char(string="Flash Pickup Ticket ID", readonly=True, copy=False, tracking=True)
    flash_staff_info_name = fields.Char(string="Flash Staff Name", readonly=True, copy=False)
    flash_staff_info_phone = fields.Char(string="Flash Staff Phone", readonly=True, copy=False)
    flash_timeout_at_text = fields.Char(string="Flash Est. Pickup Time", readonly=True, copy=False)
    flash_ticket_message = fields.Text(string="Flash System Message", readonly=True, copy=False)
    flash_pickup_notice = fields.Text(string="Flash Popup Info", readonly=True, copy=False)
    
    api_call_message = fields.Text(string="Last API Call Message", readonly=True, copy=False)

    # --- Compute and Inverse for Estimate ---
    def _compute_flash_notify_estimate_parcel_number(self):
        booking_tasks_count = self.env['warehouse.task'].search_count([('status', '=', 'booking')])
        effective_count = booking_tasks_count if booking_tasks_count > 0 else 1
        
        for record in self:
            if not record.flash_notify_estimate_manual_override:
                record.flash_notify_estimate_parcel_number = effective_count

    def _inverse_flash_notify_estimate_parcel_number(self):
        for record in self:
            record.flash_notify_estimate_manual_override = True
            _logger.info(
                f"Pickup Request {record.name or record.id}: flash_notify_estimate_parcel_number manually set to "
                f"{record.flash_notify_estimate_parcel_number}. Override flag set."
            )

    # --- Flash API Helper Methods ---
    # IMPORTANT: Consider moving these helpers to a mixin if used by multiple models (like warehouse.task)   
    def _get_system_parameter(self, param_name_suffix, env_prefix=None):
        param_value = False
        primary_key_to_try = None
        fallback_key_to_try = None

        if env_prefix:
            primary_key_to_try = f"{env_prefix}_flash_express_{param_name_suffix}"
            param_value = self.env['ir.config_parameter'].sudo().get_param(primary_key_to_try)
            if not param_value:
                fallback_key_to_try = f"flash_express_{param_name_suffix}"
                _logger.info(f"System parameter '{primary_key_to_try}' not found. Trying fallback '{fallback_key_to_try}'.")
                param_value = self.env['ir.config_parameter'].sudo().get_param(fallback_key_to_try)
        else:
            primary_key_to_try = f"flash_express_{param_name_suffix}"
            param_value = self.env['ir.config_parameter'].sudo().get_param(primary_key_to_try)

        if not param_value:
            searched_keys = f"'{primary_key_to_try}'"
            if fallback_key_to_try:
                searched_keys += f" and fallback '{fallback_key_to_try}'"
            _logger.warning(f"System parameter for suffix '{param_name_suffix}' not found. Tried: {searched_keys}.")
        
        return param_value or False

    def _create_random_string(self, length=32):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for i in range(length))

    def _filter_null_key_value(self, data):
        if not data:
            return {}
        return {k: v for k, v in data.items() if v is not None and str(v) != ""}

    def _construct_key_value_string(self, data):
        if not data:
            return ""
        sorted_keys = sorted(data.keys())
        key_value_pairs = [f"{key}={data[key]}" for key in sorted_keys]
        string_a = "&".join(key_value_pairs)
        _logger.debug(f"Signature stringA: {string_a}")
        return string_a

    def _construct_presign_string(self, key_value_string, secret_key_value):
        if not secret_key_value:
            _logger.error("Secret key (api_key) is missing for signature generation.")
            raise UserError(_("Flash Express API Secret Key is not configured."))
        string_sign_temp = f"{key_value_string}&key={secret_key_value}"
        _logger.debug(f"Signature stringSignTemp: {string_sign_temp}")
        return string_sign_temp

    def _sha256_encode(self, text_to_encode):
        encoded_text = text_to_encode.encode('utf-8')
        hashed_text = hashlib.sha256(encoded_text).hexdigest()
        _logger.debug(f"SHA256 (lowercase): {hashed_text}")
        return hashed_text

    def _transform_string_to_upper_case(self, s):
        res = s.upper()
        _logger.debug(f"Uppercase: {res}")
        return res

    # --- Notify Courier API Methods ---
    async def _call_flash_express_notify_courier_api(self, session, payload_for_post):
        self.ensure_one()
        api_env = self._get_system_parameter("api_env") or 'TRAIN' # Expects flash_express_api_env
        # Expects flash_express_train_base_url or flash_express_prod_base_url
        base_url = self._get_system_parameter(f"{api_env.lower()}_base_url") 

        if not base_url:
            _logger.error(f"Flash API base URL not configured for env '{api_env}'.")
            raise UserError(_("Flash API base URL for environment '%s' is not configured.", api_env))

        api_endpoint = "/open/v1/notify"
        api_url = f"{base_url.rstrip('/')}{api_endpoint}"
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}

        _logger.info(f"AIOHTTP Notify Courier: Sending POST to {api_url} for Pickup ID {self.name}")
        _logger.debug(f"AIOHTTP Notify Courier: Payload: {payload_for_post}")

        try:
            async with session.post(api_url, data=payload_for_post, headers=headers, timeout=30) as response:
                response_text = await response.text()
                _logger.info(f"Notify Courier Resp Status: {response.status} for Pickup ID {self.name}")
                _logger.debug(f"Notify Courier Resp Body: {response_text} for Pickup ID {self.name}")
                response.raise_for_status()
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    _logger.error(f"Notify Courier: Invalid JSON: {response_text[:500]}")
                    raise UserError(_("Invalid JSON response from Flash (Notify Courier): %s", response_text[:200]))
        except aiohttp.ClientResponseError as e:
            error_body = "N/A"
            if hasattr(e, 'response') and e.response:
                try: error_body = await e.response.text() 
                except Exception: pass
            _logger.error(f"Notify Courier HTTP error {e.status}: {e.message}. Body: {error_body}")
            # Try to parse a message from Flash's JSON error response
            flash_error_message = e.message
            if '{' in error_body and '}' in error_body: # Basic check for JSON
                try: flash_error_message = json.loads(error_body).get('message', e.message)
                except json.JSONDecodeError: pass
            raise UserError(_("Flash API Error (%s) calling courier: %s", e.status, flash_error_message))
        except asyncio.TimeoutError:
            _logger.error("AIOHTTP Notify Courier: Request timed out for Pickup ID %s.", self.name)
            raise UserError(_("The request to Flash Express (call courier) timed out."))
        except aiohttp.ClientError as e: # Other client errors like connection issues
            _logger.error(f"AIOHTTP Notify Courier: ClientError for {self.name}: {e}")
            raise UserError(_("Could not connect to Flash Express (call courier): %s", e))
        except Exception as e:
            _logger.error(f"Unexpected error calling Notify Courier for {self.name}: {e}", exc_info=True)
            raise UserError(_("Unexpected error calling Flash courier: %s", e))


    async def _prepare_and_call_notify_courier_api_async(self, session):
        self.ensure_one()
        _logger.info(f"Preparing Notify Courier call for Pickup ID: {self.name}")

        api_env_setting = self._get_system_parameter("api_env") or 'TRAIN'
        credential_env_prefix = 'prod' if api_env_setting.upper() == 'PROD' else 'dev'
        
        mch_id = self._get_system_parameter("mch_id", credential_env_prefix)
        secret_key = self._get_system_parameter("secret_key", credential_env_prefix)

        if not mch_id: raise UserError(_("Flash MCH ID for env '%s' not configured.", credential_env_prefix))
        if not secret_key: raise UserError(_("Flash Secret Key for env '%s' not configured.", credential_env_prefix))

        # Define which source parameters are needed and their suffixes for _get_system_parameter
        src_params_config = {
            "srcName": "src_name", "srcPhone": "src_phone",
            "srcProvinceName": "src_province_name", "srcCityName": "src_city_name",
            "srcPostalCode": "src_postal_code", "srcDetailAddress": "src_detail_address"
        }
        
        fetched_src_params_for_payload = {}
        for api_payload_key, sys_param_suffix in src_params_config.items():
            value = self._get_system_parameter(sys_param_suffix)
            if not value:
                raise UserError(_(
                    "Missing required sender information in system parameters. "
                    "Could not find value for '%s' (expected system parameter: 'flash_express_%s').", 
                    api_payload_key, sys_param_suffix
                ))
            fetched_src_params_for_payload[api_payload_key] = str(value)

        src_district_name_suffix = "src_district_name"
        src_district_name_val = self._get_system_parameter(src_district_name_suffix)
        if src_district_name_val:
            fetched_src_params_for_payload["srcDistrictName"] = str(src_district_name_val)
        else:
            _logger.info(f"Optional system parameter 'flash_express_{src_district_name_suffix}' not found, omitting.")

        payload_body_for_signing = {
            "mchId": str(mch_id),
            "nonceStr": self._create_random_string(32),
            **fetched_src_params_for_payload,
            "estimateParcelNumber": int(self.flash_notify_estimate_parcel_number) if self.flash_notify_estimate_parcel_number > 0 else 1,
        }
        if self.flash_pickup_remark:
            payload_body_for_signing["remark"] = str(self.flash_pickup_remark)
        
        _logger.debug(f"AIOHTTP Notify Courier: Payload body for signing: {payload_body_for_signing}")

        data_to_sign_filtered = self._filter_null_key_value(payload_body_for_signing.copy())
        key_value_request_string = self._construct_key_value_string(data_to_sign_filtered)
        presign_string = self._construct_presign_string(key_value_request_string, secret_key)
        encoded_signature = self._sha256_encode(presign_string)
        final_api_signature = self._transform_string_to_upper_case(encoded_signature)
        
        final_payload_for_post = payload_body_for_signing.copy()
        final_payload_for_post["sign"] = final_api_signature
        
        return await self._call_flash_express_notify_courier_api(session, final_payload_for_post)

    def action_call_flash_courier(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Courier can only be called for pickup requests in 'Draft' state."))
        if self.flash_notify_estimate_parcel_number <= 0:
            raise UserError(_("Please enter a valid 'Est. Parcel Count' (must be > 0)."))

        _logger.info(f"User triggered 'Call Flash Courier' for Pickup Request: {self.name}")
        
        # Set state to 'requested' immediately to prevent double calls
        # and provide feedback that the process has started.
        # The API call might still fail, then state will be set to 'failed'.
        self.write({'state': 'requested', 'api_call_message': _("Requesting courier from Flash Express...")})
        self.env.cr.commit() # Commit state change before long API call for better UX if API times out

        async def main_async_wrapper():
            async with aiohttp.ClientSession() as session:
                return await self._prepare_and_call_notify_courier_api_async(session)
        
        try:
            result = asyncio.run(main_async_wrapper())
            _logger.info(f"Notify Courier API call for {self.name} completed. Result: {result}")

            if result and isinstance(result, dict) and result.get("code") == 1 and result.get("data"):
                api_data = result.get("data")
                self.write({
                    'state': 'confirmed_by_flash', 
                    'flash_ticket_pickup_id': api_data.get("ticketPickupId"),
                    'flash_staff_info_name': api_data.get("staffInfoName"),
                    'flash_staff_info_phone': api_data.get("staffInfoPhone"),
                    'flash_timeout_at_text': api_data.get("timeoutAtText"),
                    'flash_ticket_message': api_data.get("ticketMessage"),
                    'flash_pickup_notice': api_data.get("notice"),
                    'api_call_message': _("Courier called successfully! Ticket ID: %s", api_data.get("ticketPickupId"))
                })
                success_msg = _("Courier called for %s! Ticket: %s. Staff: %s (%s). Est. Pickup: %s",
                                self.name, api_data.get("ticketPickupId"),
                                api_data.get("staffInfoName") or _("N/A"),
                                api_data.get("staffInfoPhone") or _("N/A"),
                                api_data.get("timeoutAtText") or _("N/A"))
                _logger.info(success_msg)
                # Post a message to chatter
                self.message_post(body=success_msg + (f"<br/>System Message: {api_data.get('ticketMessage')}" if api_data.get('ticketMessage') else ""))
                return {
                    'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': _('Courier Called'), 'message': success_msg, 'type': 'success', 'sticky': True}
                }
            else:
                error_msg = result.get("message", _("API call failed or returned no data.")) if result else _("No response from API.")
                self.write({'state': 'failed', 'api_call_message': error_msg})
                self.message_post(body=_("Failed to call courier: %s", error_msg))
                raise UserError(_("Flash API Error (Notify Courier): %s", error_msg))
        except UserError as ue: # Catch UserErrors from async methods or this one
            # State might have already been set to 'failed' if error came from API helper
            if self.state != 'failed':
                self.write({'state': 'failed', 'api_call_message': str(ue)})
            _logger.error(f"UserError during 'Call Flash Courier' for {self.name}: {ue}")
            self.message_post(body=_("Error calling courier: %s", str(ue)))
            raise
        except Exception as e:
            self.write({'state': 'failed', 'api_call_message': _("Unexpected system error: %s", type(e).__name__)})
            _logger.error(f"Unexpected error 'Call Flash Courier' for {self.name}: {e}", exc_info=True)
            self.message_post(body=_("System Error calling courier: %s. Check logs.", type(e).__name__))
            raise UserError(_("Unexpected system error. Check logs. (%s)", type(e).__name__))
        return True # Fallback if no specific action is returned