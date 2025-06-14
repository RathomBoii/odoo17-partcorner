# -------------------------------------------------------------------------
# IMPORTANT - HOW TO USE THIS CODE
# -------------------------------------------------------------------------
# 1. This is a Controller, not a Server Action script. It WILL NOT work
#    if pasted into the "Execute Python Code" field of a Server Action.
#
# 2. Save this file as `controllers/main.py` inside your custom Odoo module.
#    Make sure your module has a `controllers/__init__.py` file that imports this file
#    (e.g., `from . import main`).
#
# 3. Store your Flash Express Secret Key in Odoo's system parameters.
#    - Go to Settings -> Technical -> Parameters -> System Parameters.
#    - Create a new parameter with the Key: `flash_express.secret_key`
#    - Set the Value to the secret key provided by Flash Express.
#
# 4. Provide the correct URL to Flash Express for the webhook.
#    The URL will be: `https://<your_odoo_domain>/api/flash_express/webhook`
#
# 5. Customize the TASK_STATUS_MAP dictionary below to map Flash Express's
#    delivery states to your internal warehouse task statuses.
# -------------------------------------------------------------------------

import json
import logging
import hashlib
import odoo
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class FlashExpressWebhookController(http.Controller):
    """
    Controller to handle incoming webhooks from Flash Express for parcel status updates.
    """

    # --- CUSTOMIZE THIS SECTION ---
    # This dictionary maps Flash Express's integer state codes to your internal
    # `warehouse.task` status keys. You should adjust this to match your business workflow.
    # The webhook will force the task into this status.
    # Refer to Flash Express documentation for a full list of state codes.
    TASK_STATUS_MAP = {
        2: 'pick_up_by_courier',  # State 2: Courier has accepted or picked up the parcel.
        5: 'done',                # State 5: Parcel has been successfully delivered.
        6: 'done',                # State 6: Parcel is returned. You might want a different status like 'returned'.
    }
    # --- END CUSTOMIZATION ---

    def _verify_signature(self, data_str, signature):
        """
        Verifies the incoming request signature based on Flash Express documentation.
        The signature is HASH(sorted_params_string + secret_key).
        For the webhook push, the only parameter is 'data'.
        """
        secret_key = request.env['ir.config_parameter'].sudo().get_param('flash_express.secret_key')
        if not secret_key:
            _logger.error("Flash Express secret key is not set in system parameters (flash_express.secret_key).")
            return False

        # As per general signature algorithm: sort parameters, form a string 'key=value',
        # append the secret key, then calculate the hash.
        # For this webhook, the only parameter to sign is 'data'.
        string_to_sign = f"data={data_str}"
        string_to_hash = string_to_sign + secret_key

        # UPDATED: Changed from hashlib.md5 to hashlib.sha256 as requested for better security.
        m = hashlib.sha256()
        m.update(string_to_hash.encode('utf-8'))
        calculated_signature = m.hexdigest().upper()
        
        # For debugging purposes, you can check the logs if your Odoo log level is set to 'debug'
        _logger.debug(f"Flash Webhook - String to Hash: {string_to_hash}")
        _logger.debug(f"Flash Webhook - Calculated Signature: {calculated_signature}")
        _logger.debug(f"Flash Webhook - Received Signature: {signature.upper()}")

        return calculated_signature == signature.upper()

    @http.route('/api/flash_express/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def flash_express_webhook(self, **kwargs):
        """Main webhook endpoint."""
        raw_payload = request.jsonrequest
        _logger.info("Flash Express webhook received. Payload: %s", raw_payload)

        # Flash Express sends a JSON object where the 'data' field is a stringified JSON.
        # And 'authorize' is the signature.
        data_str = raw_payload.get('data')
        signature = raw_payload.get('authorize')

        if not data_str or not signature:
            _logger.error("Webhook payload is missing 'data' or 'authorize' field.")
            return {"code": 0, "message": "Invalid payload structure."}

        # 1. Verify the signature for security
        if not self._verify_signature(data_str, signature):
            _logger.warning("Webhook signature verification failed.")
            return {"code": 0, "message": "Signature verification failed."}

        try:
            # 2. Parse the tracking data and find the task
            tracking_data = json.loads(data_str)
            flash_tracking_no = tracking_data.get('pno') # 'pno' is the tracking number

            if not flash_tracking_no:
                _logger.warning("No 'pno' (tracking number) in webhook data.")
                return {"code": 1, "message": "success"} # Success, but nothing to do

            # Search for the task using the Flash tracking number, stored in 'delivery_order_id'
            task = request.env['warehouse.task'].sudo().search([('delivery_order_id', '=', flash_tracking_no)], limit=1)
            if not task:
                _logger.warning("No warehouse task found for Flash tracking no: %s", flash_tracking_no)
                return {"code": 1, "message": "success"} # Success, as the error is on our side

            # 3. Prepare and write the updates to the task
            flash_state_code = tracking_data.get('state')
            latest_route = tracking_data.get('routes', [{}])[-1]

            vals_to_update = {
                'flash_parcel_state_code': flash_state_code,
                'flash_parcel_state_text': latest_route.get('desc'),
                'flash_parcel_state_change_at': tracking_data.get('state_time'),
                'flash_parcel_routes_details': json.dumps(tracking_data.get('routes'), indent=2),
                'flash_latest_route_message': latest_route.get('desc'),
                'flash_latest_route_action': latest_route.get('action'),
                'flash_latest_route_at': latest_route.get('time'),
            }

            # Map Flash state to our internal task status, if a mapping exists
            if flash_state_code in self.TASK_STATUS_MAP:
                new_task_status = self.TASK_STATUS_MAP[flash_state_code]
                if task.status != new_task_status:
                    vals_to_update['status'] = new_task_status
                    _logger.info("Updating task %s status to '%s' based on Flash state %s", task.name, new_task_status, flash_state_code)

            task.write(vals_to_update)
            _logger.info("Successfully updated task %s for tracking no %s.", task.name, flash_tracking_no)

            # 4. Return the required success response to Flash Express
            return {"code": 1, "message": "success"}

        except json.JSONDecodeError as e:
            _logger.error("Failed to decode JSON from 'data' field: %s", e)
            return {"code": 0, "message": "JSON decode error."}
        except Exception as e:
            _logger.exception("An unexpected error occurred while processing Flash Express webhook.")
            # We still tell Flash it was a success to avoid retries for unrecoverable errors.
            # The exception is logged in Odoo for manual review.
            return {"code": 1, "message": "success"}