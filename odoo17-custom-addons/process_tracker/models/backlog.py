from odoo import models, fields, api
from odoo.exceptions import ValidationError

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
    # invoice_id = fields.Many2one('account.move',  string="Invoice ID", compute="_compute_invoice_delivery")
    # delivery_id = fields.Many2one('stock.picking',  string="Delivery Note", compute="_compute_invoice_delivery")

    # @api.depends('sale_order_id.invoice_ids', 'sale_order_id.picking_ids')
    # def _compute_invoice_delivery(self):
    #     for record in self:
    #         invoice = record.sale_order_id.invoice_ids.filtered(lambda x: x.move_type == 'out_invoice')[:1]
    #         delivery = record.sale_order_id.picking_ids.filtered(lambda x: x.picking_type_code == 'outgoing')[:1]
    #         record.invoice_id = invoice.id if invoice else False
    #         record.delivery_id = delivery.id if delivery else False

    def write(self, vals):

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
        records = self.search([('status', '=', 'order_received')])
        for record in records:
            record.write({'status': 'transitioned'})
    