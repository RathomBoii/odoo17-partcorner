from odoo import models, api, fields
import datetime
import pytz

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    current_wip_status = fields.Char(string="WIP Status", compute="_compute_current_wip_status")

    @api.depends('order_line')  # anything to trigger recompute; you can adjust this
    def _compute_current_wip_status(self):
        status_display_map = {
            'order_received': 'Preparing',
            'booking': 'On Delivery',
            'pick_up_by_courier': 'On delivery'
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

    @api.model
    def create(self, vals):
        record = super().create(vals)

        # Set timezone — for Thailand
        tz = pytz.timezone("Asia/Bangkok")
        current_time = datetime.datetime.now(tz).time()
        wip_start_time = datetime.time(6, 0)
        wip_end_time = datetime.time(12, 0)

        model = 'process.wip' if current_time <= wip_end_time and current_time >= wip_start_time else 'process.backlog'

        invoices = record.invoice_ids

        # Create WIP/Backlog without invoice and delivery initially
        process_record = self.env[model].create({
            'sale_order_id': record.id,
            'created_date': datetime.datetime.now(),
            'total': record.amount_total,
            'status': 'order_received',
            'invoice_id': invoices,
        })

        # Schedule an update after transaction completes
        # self.env.cr.postcommit.add(lambda: self._update_process_record(record, process_record))

        return record
    
    # def _update_process_record(self, sale_order, process_record):
    #     """Update process record with invoice and delivery after they're created"""
        

    #     # Get invoice using invoice_ids relationship
    #     invoice = sale_order.invoice_ids.filtered(lambda x: x.move_type == 'out_invoice')[:1]

    #     # Get delivery using picking_ids relationship
    #     delivery = sale_order.picking_ids.filtered(lambda x: x.picking_type_code == 'outgoing')[:1]

    #     if invoice or delivery:
    #         process_record.write({
    #             'invoice_id': invoice.id if invoice else False,
    #             'delivery_id': delivery.id if delivery else False,
    #         })