from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProcessWIP(models.Model):
    _name = 'process.wip'
    _description = 'Work In Progress'

    sale_order_id = fields.Many2one('sale.order', required=True, string="Sale Order ID")
    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)
    created_date = fields.Datetime(default=fields.Datetime.now, readonly=True)

    """
    These following are the possible statuses and it's number we will received from Flash Express webhook:
        1=Picked Up (รับพัสดุแล้ว)
        2=In transit (ระหว่างการขนส่ง)
        3=Delivering (ระหว่างการจัดส่ง)
        4=Detained (พัสดุคงคลัง)
        5=Signed (เซ็นรับแล้ว)
        6=Problem shipment being processed (ระหว่างจัดการพัสดุมีปัญหา)
        7=Returned shipment (พัสดุตีกลับแล้ว)
        8=Close by exception (ปิดงานมีปัญหา)
        9=Cancelled (เรียกคืนพัสดุแล้ว)
    """
    status = fields.Selection([
        ('order_received', 'Order Received'), 
        ('kitting', 'Kitting'), 
        ('checking', 'Checking'), 
        ('packing', 'Packing'),
        ('delivery_order_created', 'Delivery Order Created'),
        ('courier_pickup_requested', 'Courier Pickup Requested'),
        ('pick_up_by_courier', 'Pick Up By Courier'), 
        ('in_transit', 'In Transit'),
        ('delivering', 'Delivering'),
        ('detained', 'Detained'),
        ('signed', 'Signed'),
        ('problem_shipment_being_processed', 'Problem Shipment Being Processed'),
        ('returned_shipment', 'Returned Shipment'),
        ('close_by_exception', 'Close By Exception'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done')
    ], default='order_received')

    total = fields.Float(readonly=True, compute="_compute_invoice_delivery_total")
    invoice_id = fields.Many2one('account.move',  string="Invoice ID", compute="_compute_invoice_delivery_total")
    delivery_id = fields.Many2one('stock.picking',  string="Delivery Note", compute="_compute_invoice_delivery_total")
    
    # link to wip logs data history
    wip_log_ids = fields.One2many('process.wip.log', 'wip_id', string="WIP History", readonly="True")

    _sql_constraints = [
        ('unique_sale_order_id', 'unique(sale_order_id)', 'A WIP record can only be created for a sale order once.')
    ]

    @api.depends('sale_order_id.invoice_ids', 'sale_order_id.picking_ids')
    def _compute_invoice_delivery_total(self):
        for record in self:
            invoice = record.sale_order_id.invoice_ids.filtered(lambda x: x.move_type == 'out_invoice')[:1] # type: ignore
            delivery = record.sale_order_id.picking_ids.filtered(lambda x: x.picking_type_code == 'outgoing')[:1] # type: ignore
            total = record.sale_order_id.amount_total # type: ignore
            record.invoice_id = invoice.id if invoice else False 
            record.delivery_id = delivery.id if delivery else False
            record.total = total if total else False

    def write(self, vals):
        if 'status' in vals:
            for rec in self:
                self.env['process.wip.log'].create({
                    'wip_id': rec.id, # type: ignore
                    'previous_status': rec.status,
                    'current_status': vals['status'],
                    'changed_by': self.env.user.id
                })
        return super().write(vals)

    @api.onchange('status')
    def _onchange_status(self):


    #     status = fields.Selection([
    #     ('order_received', 'Order Received'), 
    #     ('kitting', 'Kitting'), 
    #     ('checking', 'Checking'), 
    #     ('packing', 'Packing'),
    #     ('delivery_order_created', 'Delivery Order Created'),
    #     ('courier_pickup_requested', 'Courier Pickup Requested'),
    #     ('pick_up_by_courier', 'Pick Up By Courier'), 
    #     ('in_transit', 'In Transit'),
    #     ('delivering', 'Delivering'),
    #     ('detained', 'Detained'),
    #     ('signed', 'Signed'),
    #     ('problem_shipment_being_processed', 'Problem Shipment Being Processed'),
    #     ('returned_shipment', 'Returned Shipment'),
    #     ('close_by_exception', 'Close By Exception'),
    #     ('cancelled', 'Cancelled'),
    #     ('done', 'Done')
    # ], default='order_received')


        """
        Because of the Flash Express status , we do not know how they transition the status, 
        so I define with no backward and forward transition constraint.
        In contrast for internal statuses (  'order_received', 'kitting', 'checking', 'packing', etc. ), it need to have a constraint that
        """
        allowed_status_transition_dict = {
    # These first four statuses retain their original, specific transitions
    'order_received': ['kitting'],
    'kitting': ['checking'],
    'checking': ['packing'],
    'packing': ['delivery_order_created'],

    # For the delivery statuses, each can transition to any other delivery status.
    # The key itself is excluded from its own list of possible transitions.
    'delivery_order_created': [
        'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'courier_pickup_requested': [
        'delivery_order_created', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'pick_up_by_courier': [
        'delivery_order_created', 'courier_pickup_requested', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'in_transit': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'delivering': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'detained': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'signed': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'problem_shipment_being_processed': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'returned_shipment', 'close_by_exception', 'cancelled', 'done'
    ],
    'returned_shipment': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'close_by_exception', 'cancelled', 'done'
    ],
    'close_by_exception': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'cancelled', 'done'
    ],
    'cancelled': [
        'delivery_order_created', 'courier_pickup_requested', 'pick_up_by_courier', 'in_transit', 'delivering', 'detained', 'signed', 
        'problem_shipment_being_processed', 'returned_shipment', 'close_by_exception', 'done'
    ],
    
    # 'done' is a terminal state and has no further transitions.
    'done': []
}
        for record in self:
            if record.status and record._origin.status:
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.status
                previous_status = record._origin.status
                is_valid_transition = preferred_status in allowed_status_transition_dict.get(previous_status,[]) # type: ignore
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.status}.")
    