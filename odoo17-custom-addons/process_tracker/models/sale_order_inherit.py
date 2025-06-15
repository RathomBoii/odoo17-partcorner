from odoo import models, api, fields
import datetime
import pytz
from ...common.static.status import sale_portal_status_display_map

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
    If there are no Flash Order created, display PartCorners status
    else, display Flash Express status.
    """
    @api.depends('order_line')  
    def _compute_current_wip_status(self):

        for order in self:
            latest_wip = self.env['process.wip'].search([
                ('sale_order_id', '=', order.id) # type: ignore
            ], order='created_date desc', limit=1)
            if latest_wip:
                """
                Dynamically display customer order's status based on flash_express_order_id.
                Make default to be its original status if flash_express_order_id is not set.
                """
                is_flash_express_process_started = latest_wip.flash_express_order_id
                if is_flash_express_process_started:
                    order.current_wip_status = sale_portal_status_display_map.get(latest_wip.flash_express_status, latest_wip.flash_express_status) 
                else:
                    """
                    Use mapped status if available, otherwise fallback to original
                    """
                    order.current_wip_status = sale_portal_status_display_map.get(latest_wip.status, latest_wip.status)
            else:
                """
                If no WIP record found, default to 'Order Received', for customer experience.
                """ 
                order.current_wip_status = 'Order Received' 

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