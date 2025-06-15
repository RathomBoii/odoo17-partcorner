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

    # --- All your fields remain the same ---
    is_selected = fields.Boolean(string='Is Selected?', compute='_compute_is_selected', store=True)
    pickup_request_id = fields.Many2one('warehouse.pickup_request', string='Selected in Pickup Request', readonly=True, copy=False)
    flash_exception_alert = fields.Char(string="Flash Exception Alert", compute='_compute_flash_exception_alert', help="Provides a label for UI alerts if the Flash status is an exception.")
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    process_wip_id = fields.Many2one('process.wip', string='Process WIP', required=True)
    name = fields.Char(string="Task Name", required=True)
    assignee = fields.Many2one('res.users', string='Assignee')
    status = fields.Selection(part_corner_wip_and_task_status, default='order_received')
    flash_express_status = fields.Selection(flash_express_wip_and_task_good_status + flash_express_wip_and_task_bad_status, default='pending', string="Flash Express Status")
    delivery_id = fields.Many2one('stock.picking', related='process_wip_id.delivery_id')
    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)
    shipping_partner_id = fields.Many2one('res.partner', related='sale_order_id.partner_shipping_id', string="Shipping Address", readonly=True, store=True)
    delivery_contact_name = fields.Char(related='shipping_partner_id.name', string="Contact", readonly=True, store=True)
    delivery_phone = fields.Char(related='shipping_partner_id.phone', string="Phone", readonly=True, store=True)
    delivery_email = fields.Char(related='shipping_partner_id.email', string="Email", readonly=True, store=True)
    delivery_street = fields.Char(related='shipping_partner_id.street', string="Street", readonly=True, store=True)
    delivery_street2 = fields.Char(related='shipping_partner_id.street2', string="Street 2", readonly=True, store=True)
    delivery_city = fields.Char(related='shipping_partner_id.city', string="City", readonly=True, store=True)
    delivery_state_id = fields.Many2one(related='shipping_partner_id.state_id', string="State", readonly=True, store=True)
    delivery_zip = fields.Char(related='shipping_partner_id.zip', string="ZIP Code", readonly=True, store=True)
    delivery_country_id = fields.Many2one(related='shipping_partner_id.country_id', string="Country", readonly=True, store=True)
    express_category = fields.Selection([('1' , 'ธรรมดา')], default='1', string='ประเภทการจัดส่ง:')
    article_category = fields.Selection([('3' , 'อุปกรณ์ไอที')], default='3', string='ประเภทสินค้า:')
    weight = fields.Float(string='น้ำหนักพัสดุ (กรัม):')
    insured = fields.Selection([('0', 'ไม่ซื้อ'), ('1' , 'ซื้อ')], default='0', string='ซื้อ Flash care หรือไม่:')
    cod_enabled = fields.Selection([('0', 'ไม่ใช่')], default='0', string='เป็นพัสดุ COD หรือไม่:')
    out_trade_no = fields.Char(compute="_compute_flash_api_params", string="หมายเลข Order", store=True, readonly=False)
    dst_name = fields.Char(string="ชื่อผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_phone = fields.Char(string="เบอร์โทรผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_province_name = fields.Char(string="จังหวัดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_postal_code = fields.Char(string="รหัสไปรษณีย์ของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_city_name = fields.Char(string="อำเภอของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    dst_detail_address = fields.Char(string="ที่อยู่โดยละเอียดของผู้รับ", compute="_compute_flash_api_params", store=True, readonly=False)
    delivery_order_id = fields.Char(string="หมายเลขการจัดส่ง", readonly=True)
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
    is_create_flash_order_success = fields.Boolean(readonly=True, default=False, copy=False)
    # ... other fields if any ...

    # --- COMPUTE METHODS ---
    @api.depends('pickup_request_id')
    def _compute_is_selected(self):
        for record in self:
            record.is_selected = bool(record.pickup_request_id)

    @api.depends('sale_order_id', 'shipping_partner_id')
    def _compute_flash_api_params(self):
        # ... (this method remains the same) ...
        for record in self:
            if record.sale_order_id:
                record.out_trade_no = record.sale_order_id.name # type: ignore
            if record.shipping_partner_id:
                record.dst_name = record.shipping_partner_id.name or '' # type: ignore
                record.dst_phone = record.shipping_partner_id.phone or record.shipping_partner_id.mobile or '' # type: ignore
                record.dst_province_name = record.shipping_partner_id.city or '' # type: ignore
                record.dst_city_name = record.shipping_partner_id.state_id.name or '' # type: ignore
                record.dst_postal_code = record.shipping_partner_id.zip or '' # type: ignore
                record.dst_detail_address = record.shipping_partner_id.street or '' # type: ignore
                if record.shipping_partner_id.street2: # type: ignore
                    record.dst_detail_address += " " + record.shipping_partner_id.street2 # type: ignore

    @api.depends('flash_express_status')
    def _compute_flash_exception_alert(self):
        # ... (this method remains the same) ...
        happy_statuses = {'pending', 'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'signed'}
        for task in self:
            if task.flash_express_status and task.flash_express_status not in happy_statuses:
                task.flash_exception_alert = 'EXCEPTION'
            else:
                task.flash_exception_alert = False

    # --- ONCHANGE METHODS (FOR UI VALIDATION ONLY) ---
    @api.onchange('status', 'flash_express_status')
    def _onchange_status_validation(self):
        # ... (your onchange validation method remains here, unchanged) ...
        # Its job is only to provide instant feedback and errors in the UI.
        for record in self:
            if not wip_and_task_allowed_status_transition:
                raise ValidationError("Status transition rules are not defined.")

            if record.status and record._origin.status and record.status != record._origin.status:
                previous_status = record._origin.status
                preferred_status = record.status
                allowed_transitions = wip_and_task_allowed_status_transition.get(previous_status, []) # type: ignore
                if preferred_status not in allowed_transitions:
                    raise ValidationError(f"ไม่สามารถเปลี่ยนสถานะข้ามขั้นตอนได้ จาก '{previous_status}' ไปสู่ '{preferred_status}'.")
                if preferred_status == "kitting" and not record.is_delivery_note_printed:
                    record.status = previous_status
                    raise ValidationError("ไม่สามารถเปลี่ยนสถานะเป็น 'kitting' ได้ เนื่องจากยังไม่ได้ปริ้น Delivery Note.")

            if record.flash_express_status and record._origin.flash_express_status and record.flash_express_status != record._origin.flash_express_status:
                previous_flash_status = record._origin.flash_express_status
                preferred_flash_status = record.flash_express_status
                allowed_flash_transitions = wip_and_task_allowed_status_transition.get(previous_flash_status, []) # type: ignore
                if preferred_flash_status not in allowed_flash_transitions:
                    record.flash_express_status = previous_flash_status
                    raise ValidationError(f"ไม่สามารถเปลี่ยนสถานะ Flash Express ข้ามขั้นตอนได้ จาก '{previous_flash_status}' ไปสู่ '{preferred_flash_status}'.")

    # --- HELPER METHODS ---
    def _get_flash_helper(self):
        return FlashExpressHelper(self.env)

    def _get_flash_service(self):
        flash_helper = self._get_flash_helper()
        return FlashExpressService(flash_helper)
        
    # --- ACTION METHODS (Button Clicks) ---
    def print_delivery_note_inherit(self):
        self.ensure_one()
        stock_picking_to_print = self.sale_order_id.picking_ids.filtered(  # type: ignore
            lambda p: p.state != 'cancel' and p.picking_type_id.code == "outgoing"
        )
        if not stock_picking_to_print:
            raise UserError(_("There are no relevant delivery orders to print for this sales order."))
        
        stock_picking_to_print.do_print_picking()

        # SIMPLIFIED: Only write to self. The main write() method will handle the sync.
        self.write({
            'is_delivery_note_printed': True,
            'status': 'kitting'
        })

    def action_create_flash_express_order(self):
        self.ensure_one()
        flash_service = self._get_flash_service()
        try:
            result = flash_service.create_order(self)
            if result and result.get("code") == 1 and result.get("data"):
                api_data = result.get('data')
                pno = api_data.get("pno") # type: ignore
                
                # SIMPLIFIED: Only write to self. The main write() method handles the sync.
                self.write({
                    'is_create_flash_order_success': True,
                    'delivery_order_id': pno,
                    'flash_express_status': 'courier_pickup_requested',
                    'flash_express_order_id': pno, # Assuming this field exists on process_wip
                })
                # ... return action to refresh view ...
            # ... (rest of your error handling) ...
        except Exception as e:
            # ... (your exception handling) ...
            _logger.error(f"Task {self.name}: Unexpected error creating Flash order: {e}", exc_info=True)
            raise UserError(_("An unexpected system error occurred: %s", str(e)))

    # ... (action_print_label and action_check_flash_status remain the same) ...
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

    # --- ORM METHODS (CREATE, WRITE) ---
    def write(self, vals):
        # First, save the changes to the current model (warehouse.task)
        res = super().write(vals)

        # --- Handle Side Effects and Synchronization AFTER the write ---

        # 1. Sync specified fields to the related process.wip
        if not self.env.context.get('from_wip'): # Prevent echo loop
            fields_to_sync = ['status', 'flash_express_status', 'flash_express_order_id']
            sync_vals = {key: vals[key] for key in fields_to_sync if key in vals}
            
            if sync_vals:
                for record in self:
                    if record.process_wip_id:
                        record.process_wip_id.with_context(from_task=True).write(sync_vals) # type: ignore

        # 2. Automate internal status when Flash Express is 'signed'
        if vals.get('flash_express_status') == 'signed':
            for record in self:
                if record.status != 'done':
                    # This write will be caught by the sync logic above and sent to process.wip
                    record.write({'status': 'done'})

        return res
    

