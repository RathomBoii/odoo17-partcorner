from odoo import models, fields, api
from odoo.exceptions import ValidationError
import pytz
from datetime import datetime, time

class ProcessBacklog(models.Model):
    _name = 'process.backlog'
    _description = 'Backlog Process'

    sale_order_id = fields.Many2one('sale.order', required=True, readonly=True)
    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)
    created_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    total = fields.Float(readonly=True)
    status = fields.Selection([
        ('order_received', 'Order Received'), ('transitioned', 'Transitioned')
    ], default='pending')
    invoice_id = fields.Many2one('account.move', domain=[('move_type', '=', 'out_invoice')], readonly=True)
    delivery_id = fields.Many2one('stock.picking', domain=[('picking_type_code', '=', 'outgoing')], 
                            readonly=True, string="Delivery Note")


    def write(self, vals):

        # get current status
        # get new status (val)
        # conditioning process


        result = super().write(vals)  # Update status first
        if vals.get('status') == 'transitioned':
            for rec in self:
                self.env['process.wip'].create({
                    'sale_order_id': rec.sale_order_id.id,
                    'created_date': fields.Datetime.now(),
                    'total': rec.total,
                    'status': 'order_received',
                    'invoice_id': rec.invoice_id.id,
                })
        return result

    @api.onchange('status')
    def _onchange_status(self):
        allowed_status_transition_dict = {
            'order_received': ['transitioned'],
            'transitioned': []
        }
        for record in self:
            if record.status and record._origin.status:
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.status
                previous_status = record._origin.status
                is_valid_transition = preferred_status in allowed_status_transition_dict.get(previous_status,[])
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.status}.")


    @api.model
    def auto_transition_status(self):
        #/
        # Set timezone
        # set process.wip start time (6 am - 12 pm)
        # check if current time is in range
        # if current time is in range:
        #    get all records with status 'order_received' and change status to 'transitioned' 
        # timezone = pytz.timezone('Asia/Bangkok')
        # current_time = datetime.now(timezone).time()

        # start_time = time(19, 0)
        # end_time = time(23, 0)

        # if start_time <= current_time <= end_time:
        #     records = self.search([('status', '=', 'order_received')])
        #     for record in records:
                # record.write({'status': 'transitioned'})
        records = self.search([('status', '=', 'order_received')])
        for record in records:
            record.write({'status': 'transitioned'})
    