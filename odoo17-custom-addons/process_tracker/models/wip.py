from odoo import models, fields, api
from odoo.exceptions import ValidationError
import uuid

class ProcessWIP(models.Model):
    _name = 'process.wip'
    _description = 'Work In Progress'

    sale_order_id = fields.Many2one('sale.order', required=True, string="Sale Order ID")
    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)
    # related='sale_order_id.partner_id' => which partner_id to fetch
    # fields.Many2one('res.partner' => which model to fetch
    # customer = fields.Char(related='sale_order_id.partner_id.name', string="Customer", readonly=True)
    created_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    total = fields.Float(readonly=True)
    status = fields.Selection([
        ('order_received', 'Order Received'), 
        ('kitting', 'Kitting'), 
        ('checking', 'Checking'), 
        ('packing', 'Packing'),
        ('booking', 'Booking'), 
        ('pick_up_by_courier', 'Pick Up By Courier'), 
        ('done', 'Done')
    ], default='order_received')
    invoice_id = fields.Many2one('account.move', domain=[('move_type', '=', 'out_invoice')], readonly=True, string="Invoice ID")
    delivery_id = fields.Many2one('stock.picking', domain=[('picking_type_code', '=', 'outgoing')], 
                            readonly=True, string="Delivery Note")
    pickup_date = fields.Datetime(string="Courier Pick Up Date")
    delivered_date = fields.Datetime()

    # token for qr code scaning
    token = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)

    # link to wip logs data history
    wip_log_ids = fields.One2many('process.wip.log', 'wip_id', string="WIP History", readonly="True")
    

    def write(self, vals):
        if 'status' in vals:
            for rec in self:
                self.env['process.wip.log'].create({
                    'wip_id': rec.id,
                    'previous_status': rec.status,
                    'current_status': vals['status'],
                    'changed_by': self.env.user.id
                })
        return super().write(vals)

    @api.onchange('status')
    def _onchange_status(self):
        allowed_status_transition_dict = {
            'order_received': ['kitting'],
            'kitting': ['checking'],
            'checking': ['packing'],
            'packing': ['booking'],
            'booking': ['pick_up_by_courier'],
            'pick_up_by_courier': ['done'],
            'done': []
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
    