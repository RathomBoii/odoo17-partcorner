from odoo import models, api, fields
import datetime
import pytz
from odoo.exceptions import UserError

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    current_wip_status = fields.Char(string="WIP Status", compute="_compute_current_wip_status")

    def action_confirm(self):
        res = super().action_confirm()

        for sale_order in self:
            delivery_notes = self.env['stock.picking'].search(
                [
                    ('origin', '=', sale_order.name )
                ]
            )
            for delivery_note in delivery_notes:
                delivery_note.button_validate()
        return res


    @api.depends('order_line')  # anything to trigger recompute; you can adjust this
    def _compute_current_wip_status(self):
        status_display_map = {
            'order_received': 'Preparing',
            'kitting': 'Preparing',
            'checking': 'Preparing',
            'packing': 'Packing',
            'booking': 'On Delivery',
            'pick_up_by_courier': 'On delivery',
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

    # override Sale.order's create() method
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