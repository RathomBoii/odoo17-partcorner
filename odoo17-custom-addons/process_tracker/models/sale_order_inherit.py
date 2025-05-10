from odoo import models, api, fields
import datetime
import pytz
from odoo.exceptions import UserError

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    current_wip_status = fields.Char(string="WIP Status", compute="_compute_current_wip_status")


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



        # picking_ids = record.sale_order_id.picking_ids.filtered(lambda x: x.picking_type_code == 'outgoing')[:1]
        picking_ids = record.sale_order_id.picking_ids

        # correct_picking_ids =  picking_ids.mapped('package_level_ids').filtered(lambda pl: pl.state == 'draft' and not pl.move_ids)

        # Auto-validate the picking
        try:
            # picking.action_confirm()  # Confirm the picking
            # picking.action_assign()   # Assign the picking (reserve products)
            # # Check if the picking is ready to be processed
            # if picking.state in ('assigned', 'partially_available', 'waiting'): #modified condition
            #     # Process the picking to create move lines if they don't exist
            #     if not picking.move_line_ids:
            #         picking.action_generate_picking_lines()

            #     # Loop through each move line and set the quantity done
            #     for move_line in picking.move_line_ids:
            #         move_line.qty_done = move_line.product_uom_qty
                for picking_id in picking_ids:
                    picking_id.action_done()        # Validate the picking
        except Exception as e:
            # Handle any errors during validation
            raise UserError(f"Error auto-validating picking {picking_id.name}: {e}")

        return record