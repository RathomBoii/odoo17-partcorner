
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import json
import base64

from ..utils.common.flash_express_helper import FlashExpressHelper
from ..infrastructure.adapter.service.flash_express.flash_express_service import FlashExpressService
from ...common.static.status import part_corner_wip_and_task_status, flash_express_wip_and_task_good_status, flash_express_wip_and_task_bad_status
from ...common.static.status_rules import wip_and_task_allowed_status_transition

_logger = logging.getLogger(__name__)

class WarehouseTask(models.Model):
    _name = 'warehouse.task'
    _description = 'Warehouse Task'

    is_selected = fields.Boolean(string='Is Selected?', compute='_compute_is_selected', store=True)
    pickup_request_id = fields.Many2one(
        'warehouse.pickup_request',
        string='Selected in Pickup Request',
        readonly=True,
        copy=False,  # Don't copy this relationship when duplicating a resource
    )
    
    """
    pickup_request_id = fields.Many2one(
        comodel_name='warehouse.pickup_request', # Links to your main model
        string='Warehouse Pickup Request',
        ondelete='cascade',  # Or 'set null' depending on how you want to handle deletion.
                        - 'cascade' will delete linked tasks if the pickup request is deleted.
                        - 'set null' will set this field to null if the pickup request is deleted.
        index=True,     - Good for performance if you search/filter by this field
        copy=False      - Usually, you don't want to copy this link when duplicating a task
     )
    """

    flash_exception_alert = fields.Char(
        string="Flash Exception Alert",
        compute='_compute_flash_exception_alert',
        help="Provides a label for UI alerts if the Flash status is an exception."
    )

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    process_wip_id = fields.Many2one('process.wip', string='Process WIP', required=True)
    name = fields.Char(string="Task Name", required=True)
    assignee = fields.Many2one('res.users', string='Assignee')
    status = fields.Selection(part_corner_wip_and_task_status, default='order_received')
    flash_express_status = fields.Selection(flash_express_wip_and_task_good_status + flash_express_wip_and_task_bad_status, default='pending', string="Flash Express Status", help="This field is used to track the status of the Flash Express delivery. All available statuses are list from Flash Express API. 'Pending' mean there are nor Flash Order created.")

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

    """
    These are the available Flash Express's express categories, but right now we only support '1' (ธรรมดา) for normal delivery.
        ('2' , 'On-Time Delivery'),
        ('4' , 'ราคาพิเศษสำหรับพัสดุขนาดใหญ่'),
        ('6' , 'Happy Return'),
        ('7' , 'Happy Return Bulky'),
    """
    express_category = fields.Selection([
        ('1' , 'ธรรมดา'),
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
        # ( '1' , 'ใช่' )
    ], default='0', string='เป็นพัสดุ COD หรือไม่:')
    
    out_trade_no = fields.Char(compute="_compute_flash_api_params", string="หมายเลข Order", store=True, readonly=False) # readonly=False if you want it editable or only set by compute
    dst_name = fields.Char(string="ชื่อผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_phone = fields.Char(string="เบอร์โทรผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_province_name = fields.Char(string="จังหวัดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    # dst_province_name = fields.Many2one( 
    #     comodel_name='res.country.state',
    #     string='Province (Thailand)',
    #     domain="[('country_id.code', '=', 'TH')]", # Filter by Thailand's country code
    #     help="Select the province in Thailand.",
    #     # compute='_compute_flash_api_params', 
    #     store=True, 
    #     readonly=False
    # )

    dst_postal_code = fields.Char(string="รหัสไปรษณีย์ของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_city_name = fields.Char(string="อำเภอของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_detail_address = fields.Char(string="ที่อยู่โดยละเอียดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)

    delivery_order_id = fields.Char(string="หมายเลขการจัดส่ง", compute="_compute_flash_api_params", store=True, readonly=True)
    
    printed_label_pdf = fields.Binary(string="Label File (PDF):", readonly=True, attachment=False)
    printed_label_filename = fields.Char(string="Label Filename", readonly=True, default="flash_label.pdf")

    flash_parcel_state_code = fields.Integer(string="Flash State Code", readonly=True, copy=False)
    flash_parcel_state_text = fields.Char(string="Flash Parcel State", readonly=True, copy=False)
    flash_parcel_state_change_at = fields.Datetime(string="Flash State Last Updated", readonly=True, copy=False)
    flash_parcel_routes_details = fields.Text(string="Flash Route Details (JSON)", readonly=True, copy=False)

    flash_latest_route_message = fields.Char(string="Latest Route Message", readonly=True, copy=False)
    flash_latest_route_action = fields.Char(string="Latest Route Action", readonly=True, copy=False)
    flash_latest_route_at = fields.Datetime(string="Latest Route Timestamp", readonly=True, copy=False)

    is_delivery_note_printed = fields.Boolean(readonly=True, default=False, copy=False)
    thailand_province_id = fields.Many2one(
        comodel_name='res.country.state',
        string='Province (Thailand)',
        domain="[('country_id.code', '=', 'TH')]", # Filter by Thailand's country code
        help="Select the province in Thailand."
    )

    country_id = fields.Many2one(
        'res.country',
        related='thailand_province_id.country_id',
        string='Country',
        store=True, # Store for better performance if you filter by it
        readonly=True
    )
    is_create_flash_order_success = fields.Boolean(readonly=True, default=False, copy=False)

    #  Add a compute method for determine whether record are available for pickup_request model or not.
    @api.depends('pickup_request_id')
    def _compute_is_selected(self):
        for record in self:
            record.is_selected  = bool(record.pickup_request_id)
    
    # The constraint on 'pickup_request_id' is also good, but can be simplified if you rely on the Odoo ORM's handling.
    # The constraint in PickupRequest: _check_unique_tasks will be more robust.
    @api.constrains('pickup_request_id')
    def _check_single_pickup_request_id(self):
        for record in self:
            # The logic here is already handled by the _check_unique_tasks on the pickup_request side
            # This constraint isn't strictly necessary if _check_unique_tasks is robust.
            # You might remove this if the _check_unique_tasks in pickup_request is sufficient.
            pass

    @api.depends('sale_order_id', 'shipping_partner_id') # Add relevant dependencies
    def _compute_flash_api_params(self):
        for record in self:
            if record.sale_order_id:
                record.out_trade_no = record.sale_order_id.name # type: ignore
            if record.shipping_partner_id:
                record.dst_name = record.shipping_partner_id.name or '' # type: ignore
                # Populate other dst_ fields similarly
                record.dst_phone = record.shipping_partner_id.phone or record.shipping_partner_id.mobile or '' # type: ignore
                record.dst_province_name = record.shipping_partner_id.city or '' # type: ignore
                record.dst_city_name = record.shipping_partner_id.state_id.name or '' # type: ignore
                record.dst_postal_code = record.shipping_partner_id.zip or '' # type: ignore
                record.dst_detail_address = record.shipping_partner_id.street or '' # type: ignore
                if record.shipping_partner_id.street2: # type: ignore
                    record.dst_detail_address += " " + record.shipping_partner_id.street2 # type: ignore

    def write(self, vals):
        # Synchronize status changes with process.wip
        if 'status' in vals and not self.env.context.get('from_wip'):
            for record in self:
                if record.process_wip_id:
                    record.process_wip_id.with_context(from_task=True).write({'status': vals['status']}) # type: ignore
        if 'flash_express_status' in vals and not self.env.context.get('from_wip'):
            for record in self:
                if record.process_wip_id:
                    record.process_wip_id.with_context(from_task=True).write({'flash_express_status': vals['flash_express_status']}) # type: ignore
        return super().write(vals)
    # def write(self, vals):
    #     # First, call the original write method to save the changes
    #     res = super().write(vals)

    #     # Now, handle the synchronization logic after the save is complete
    #     # This is more robust than using @onchange for cross-model updates

    #     # --- Sync internal 'status' and 'flash_express_status' to process.wip ---
    #     if 'status' in vals or 'flash_express_status' in vals:
    #         if not self.env.context.get('from_wip'): # Prevent looping back
    #             sync_vals = {}
    #             if 'status' in vals:
    #                 sync_vals['status'] = vals['status']
    #             if 'flash_express_status' in vals:
    #                 sync_vals['flash_express_status'] = vals['flash_express_status']

    #             for record in self:
    #                 if record.process_wip_id and sync_vals:
    #                     record.process_wip_id.with_context(from_task=True).write(sync_vals)

    #     # --- Automatically set 'status' to 'done' when 'flash_express_status' becomes 'signed' ---
    #     if 'flash_express_status' in vals and vals['flash_express_status'] == 'signed':
    #         for record in self:
    #             # Update its own status and the related WIP's status
    #             if record.status != 'done':
    #                 record.write({'status': 'done'}) # This will trigger the sync logic above

    #     return res

    @api.onchange('express_category')
    def _onchange_sale_order_id(self):
        for record in self:
            if record.express_category:
                    record.express_category = '1'
                    return {'domain': {'expres_category': "[('id', 'in', ['1'])]"}}

    @api.onchange('status', 'flash_express_status')
    def _onchange_status_validation(self):
        """
        This method validates status transitions for both the internal status
        and the Flash Express status whenever either field is changed in the UI.
        """
        for record in self:
            # First, ensure the transition rules are loaded.
            if not wip_and_task_allowed_status_transition:
                raise ValidationError("Status transition rules are not defined.")
    
            # --- Block 1: Handle changes to the internal 'status' field ---
            if record.status and record._origin.status and record.status != record._origin.status:
                previous_status = record._origin.status
                preferred_status = record.status
    
                # General transition validation
                allowed_transitions = wip_and_task_allowed_status_transition.get(previous_status, []) # type: ignore
                if preferred_status not in allowed_transitions:
                    raise ValidationError(
                        f"ไม่สามารถเปลี่ยนสถานะข้ามขั้นตอนได้ จาก '{previous_status}' ไปสู่ '{preferred_status}'."
                    )
    
                # Specific business rule for 'booking'
                # if preferred_status == "booking":
                #     if not record.is_create_flash_order_success:
                #         # Reset the status back to its original state before raising the error
                #         record.status = previous_status
                #         raise ValidationError("ไม่สามารถเปลี่ยนสถานะเป็น 'booking' ได้ เนื่องจากยังไม่ได้สร้าง Flash Express order.")
    
                # Specific business rule for 'kitting'
                if preferred_status == "kitting":
                    if not record.is_delivery_note_printed:
                        # Reset the status back to its original state
                        record.status = previous_status
                        raise ValidationError("ไม่สามารถเปลี่ยนสถานะเป็น 'kitting' ได้ เนื่องจากยังไม่ได้ปริ้น Delivery Note.")
    
            # --- Block 2: Handle changes to the 'flash_express_status' field ---
            if record.flash_express_status and record._origin.flash_express_status and record.flash_express_status != record._origin.flash_express_status:
                previous_flash_status = record._origin.flash_express_status
                preferred_flash_status = record.flash_express_status
    
                # General transition validation for Flash Express statuses
                allowed_flash_transitions = wip_and_task_allowed_status_transition.get(previous_flash_status, []) # type: ignore
                if preferred_flash_status not in allowed_flash_transitions:
                    # Reset the status back to its original state
                    record.flash_express_status = previous_flash_status
                    raise ValidationError(
                        f"ไม่สามารถเปลี่ยนสถานะ Flash Express ข้ามขั้นตอนได้ จาก '{previous_flash_status}' ไปสู่ '{preferred_flash_status}'."
                    )

    @api.onchange('flash_express_status')
    def _onchange_flash_express_status(self): 
        for record in self:
            if record.flash_express_status and record._origin.flash_express_status:
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.flash_express_status
                previous_status = record._origin.flash_express_status
                is_valid_transition = preferred_status in wip_and_task_allowed_status_transition.get(previous_status, [])  # type: ignore
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.flash_express_status}.")

    def print_delivery_note_inherit(self):
        self.ensure_one() # Process one sale order at a time from the button

        stock_picking_to_print = self.sale_order_id.picking_ids.filtered( # type: ignore
            lambda p: p.state not in ['cancel'] and p.picking_type_id.code == "outgoing"
        )

        if not stock_picking_to_print:
            raise UserError(_("There are no relevant delivery orders to print for this sales order."))
        
        stock_picking_to_print.do_print_picking()

        self.write({
            'is_delivery_note_printed': True,
            'status': 'kitting'
            })

        # Update same status to process.wip
        for record in self:
            if record.process_wip_id:
                record.process_wip_id.with_context(from_task=True).write({ # type: ignore
                    'status': 'kitting'
                })

        stock_picking_to_print.do_print_picking()
        # report_action = stock_picking_to_print.do_print_picking()

        # if report_action:
        #     return report_action
        # else:
        #     # Fallback or logging if no action is returned (e.g., if all pickings were already printed and method was customized)
        #     # For standard 'do_print_picking', this else block might not be strictly necessary
        #     # as it always aims to return the report action.
        #     # You might want to refresh the view or provide feedback.
        #     return True # Or raise a specific UserError if expected action not received.


    # Helper to get service instances
    def _get_flash_helper(self):
        return FlashExpressHelper(self.env)

    def _get_flash_service(self):
        flash_helper = self._get_flash_helper()
        return FlashExpressService(flash_helper)

    # --- Create Order Action ---
    def action_create_flash_express_order(self):
        self.ensure_one()
        _logger.info(f"Task {self.name}: User triggered Flash Express order creation.")

        _logger.info(f"record data {self}")
        
        flash_service = self._get_flash_service()
        try:
            result = flash_service.create_order(self)
            _logger.info(f"result JSON {result}")
            _logger.info(f"Task {self.name}: Create order API result: {result}")

            if result and isinstance(result, dict):
                if result.get("code") == 1 and result.get("data"): # Flash API success
                    api_data =  result.get('data')
                    pno = api_data["pno"] # type: ignore

                    self.write({
                        'is_create_flash_order_success': True,
                        'delivery_order_id': pno,
                        'flash_express_status': 'courier_pickup_requested',
                    })

                    # Backward manipulate flash_express_order_id to process_wip 
                    for record in self:
                        if record.process_wip_id: 
                            record.process_wip_id.with_context(from_task=True).write({ # type: ignore
                                'flash_express_order_id': pno,
                                'flash_express_status': 'courier_pickup_requested'
                                }) 

                    # This is generally the most reliable way to see updated data.
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': self._name,
                        'res_id': self.id, # type: ignore
                        'view_mode': 'form',
                        'views': [[False, 'form']], # You can specify a particular form view ID if needed: [[view_id, 'form']]
                        'target': 'current', # Reopens in the current view, effectively refreshing it
                        # Optionally, you can still send a notification before reloading
                        # by returning a list of actions or by using the bus.
                        # For simplicity, a direct reload is shown here.
                        # If you want a notification first, it's more complex; usually, a reload is enough.
                    }
                elif result.get("code") == 0 and "already exists" in result.get("message", "").lower(): # Specific case
                    return {
                        'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {
                            'title': _('Information'), 'message': result.get("message"),
                            'type': 'info', 'sticky': False,
                        }}
                else: # Flash API business error
                    error_message = result.get("message", "API call failed or returned unexpected data.")
                    raise UserError(_("Flash Express API Error: %s", error_message))
            else: # Unexpected response format from service
                raise UserError(_("Flash Express API call returned an unexpected result format."))
        except UserError as ue: # Catch UserErrors from service or here
            _logger.error(f"Task {self.name}: UserError creating Flash order: {ue}")
            raise # Re-raise for Odoo to display
        except Exception as e:
            _logger.error(f"Task {self.name}: Unexpected error creating Flash order: {e}", exc_info=True)
            raise UserError(_("An unexpected system error occurred: %s", str(e)))

    # --- Print Label Action ---
    def action_print_label_flash_express_order(self):
        self.ensure_one()
        _logger.info(f"Task {self.name}: User triggered print label for PNO {self.delivery_order_id}.")

        if not self.delivery_order_id: # Should be caught by service too, but good pre-check
            raise UserError(_("Flash Express PNO is not set. Cannot print label."))

        flash_service = self._get_flash_service()
        try:
            pdf_bytes = flash_service.print_label(self)
            if pdf_bytes:
                pdf_base64 = base64.b64encode(pdf_bytes)
                filename = f"FlashLabel_{str(self.delivery_order_id).replace('/', '_')}_{str(self.name).replace('/', '_')}.pdf"
                self.write({
                    'printed_label_pdf': pdf_base64,
                    'printed_label_filename': filename,
                })
                return { # Action to download the PDF
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{self._name}/{self.id}/printed_label_pdf?download=true&filename={self.printed_label_filename}', # type: ignore
                    'target': 'self', # Download in current tab
                }
            else: # Should not happen if service raises error on empty PDF
                _logger.error(f"Task {self.name}: Print label returned no data.")
                raise UserError(_("Failed to retrieve PDF label: No data received from Flash Express."))
        except UserError as ue:
            _logger.error(f"Task {self.name}: UserError printing label: {ue}")
            raise
        except Exception as e:
            _logger.error(f"Task {self.name}: Unexpected error printing label: {e}", exc_info=True)
            raise UserError(_("An unexpected system error occurred while printing label: %s", str(e)))

    # --- Check Status Action ---
    def action_check_flash_status(self):
        self.ensure_one()
        _logger.info(f"Task {self.name}: User triggered status check for PNO {self.delivery_order_id}.")

        if not self.delivery_order_id:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _("Flash Express PNO (Tracking ID) is not set."),
                    'type': 'danger', 'sticky': False,
                }}

        flash_service = self._get_flash_service()
        try:
            result = flash_service.check_status(self)
            _logger.info(f"Task {self.name}: Check status API result: {result}")

            if result and isinstance(result, dict):
                if result.get("code") == 1 and result.get("data"): # Flash API success
                    api_data = result.get("data")
                    pno_returned = api_data.get("pno") # type: ignore
                    state_code = api_data.get("state") # type: ignore
                    state_text = api_data.get("stateText") # type: ignore
                    state_change_at_str = api_data.get("stateChangeAt") # type: ignore
                    routes = api_data.get("routes") or [] # type: ignore

                    vals_to_write = {
                        'flash_parcel_state_code': state_code,
                        'flash_parcel_state_text': state_text,
                        'flash_parcel_routes_details': json.dumps(routes, indent=2) if routes else "[]",
                        'flash_parcel_state_change_at': fields.Datetime.to_datetime(state_change_at_str) if state_change_at_str else False,
                    }
                    if routes: # Process latest route
                        latest_route = routes[0] # Assuming sorted: most recent first
                        latest_route_at_str = latest_route.get('routedAt')
                        vals_to_write.update({
                            'flash_latest_route_message': latest_route.get('message'),
                            'flash_latest_route_action': latest_route.get('routeAction'),
                            'flash_latest_route_at': fields.Datetime.to_datetime(latest_route_at_str) if latest_route_at_str else False,
                        })
                    else: # Clear if no routes
                        vals_to_write.update({
                            'flash_latest_route_message': False,
                            'flash_latest_route_action': False,
                            'flash_latest_route_at': False,
                        })
                    self.write(vals_to_write)
                    return {
                        'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {
                            'title': _('Status Updated'),
                            'message': _("Flash PNO %s: %s", pno_returned, state_text),
                            'type': 'success', 'sticky': False,
                        }}
                else: # Flash API business error
                    error_message = result.get("message", "API call failed or returned unexpected data.")
                    raise UserError(_("Flash Express API Error: %s", error_message))
            else: # Unexpected response format
                raise UserError(_("Flash Express API (check status) returned an unexpected result format."))
        except UserError as ue:
            _logger.error(f"Task {self.name}: UserError checking status: {ue}")
            raise
        except Exception as e:
            _logger.error(f"Task {self.name}: Unexpected error checking status: {e}", exc_info=True)
            raise UserError(_("An unexpected system error occurred while checking status: %s", str(e)))

    # ... (other model methods like _compute_flash_api_params, write, onchanges, etc. remain)
    # Ensure the methods _get_system_parameter, _create_random_string, etc.
    # are REMOVED from this model file as they are now in FlashExpressHelper.   