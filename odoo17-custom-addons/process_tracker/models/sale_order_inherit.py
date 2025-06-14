from odoo import models, api, fields
import datetime
import pytz
from odoo.exceptions import UserError

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    current_wip_status = fields.Char(string="WIP Status", compute="_compute_current_wip_status")

    def action_confirm(self):
        res = super().action_confirm() # type: ignore

        for sale_order in self:
            delivery_notes = self.env['stock.picking'].search(
                [
                    ('origin', '=', sale_order.name ) # type: ignore
                ]
            )
            for delivery_note in delivery_notes:
                delivery_note.button_validate()
        return res


    """
    This method map the wip (also warehouse.task)'s status and sale order status which display on the sale portal view that user will see on web site.
    """
    @api.depends('order_line')  
    def _compute_current_wip_status(self):
        status_display_map = {
            'order_received': 'Preparing',
            'kitting': 'Preparing',
            'checking': 'Preparing',
            'packing': 'Packing',
            'delivery_order_created': 'Ready to ship',
            'courier_pickup_requested': 'Courier is going to pick up',
            'pick_up_by_courier': 'Courier picked up',
            'in_transit': 'In Transit',
            'delivering': 'Delivering',
            'detained': 'Detained',
            'signed': 'Delivered',
            'problem_shipment_being_processed': 'Problem Shipment Being Processed',
            'returned_shipment': 'Returned Shipment',
            'close_by_exception': 'Close By Exception',
            'cancelled': 'Cancelled',
            'done': 'Delivered'
        }

        for order in self:
            latest_wip = self.env['process.wip'].search([
                ('sale_order_id', '=', order.id)
            ], order='created_date desc', limit=1)
            if latest_wip:
            # Use mapped status if available, otherwise fallback to original
                order.current_wip_status = status_display_map.get(latest_wip.status, latest_wip.status)
            else:
                order.current_wip_status = ''

    """
    This method determine the which corresponding record will be created  
    based on occur sale order at the time of creation. (create wip or backlog)  
    """
    @api.model
    def create(self, vals):
        record = super().create(vals)

        # Set timezone — for Thailand
        tz = pytz.timezone("Asia/Bangkok")

        current_time = datetime.datetime.now(tz).time()
        wip_start_time = datetime.time(6,0)
        wip_end_time = datetime.time(12, 0)


        if current_time <= wip_end_time and current_time >= wip_start_time:
            model = 'process.wip'
        else:
            model = 'process.backlog'


        # compare to JS -> db.model["key"].create
        self.env[model].create({
            'sale_order_id': record.id,
            'created_date': datetime.datetime.now(),
            'status': 'order_received',
        })

        return record