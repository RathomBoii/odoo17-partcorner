from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ...common.static.status_rules import wip_and_task_allowed_status_transition
from ...common.static.status import part_corner_wip_and_task_status, flash_express_wip_and_task_good_status, flash_express_wip_and_task_bad_status

class ProcessWIP(models.Model):
    _name = 'process.wip'
    _description = 'Work In Progress'

    sale_order_id = fields.Many2one('sale.order', required=True, string="Sale Order ID")
    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)
    created_date = fields.Datetime(default=fields.Datetime.now, readonly=True)

    
    status = fields.Selection(part_corner_wip_and_task_status, default='order_received')
    flash_express_status = fields.Selection(flash_express_wip_and_task_good_status + flash_express_wip_and_task_bad_status, default='pending', string="Flash Express Status", help="This field is used to track the status of the Flash Express delivery. All available statuses are list from Flash Express API. 'Pending' mean there are nor Flash Order created.")

    total = fields.Float(readonly=True, compute="_compute_invoice_delivery_total")
    invoice_id = fields.Many2one('account.move',  string="Invoice ID", compute="_compute_invoice_delivery_total")
    delivery_id = fields.Many2one('stock.picking',  string="Delivery Note", compute="_compute_invoice_delivery_total")
    
    # link to wip logs data history
    wip_log_ids = fields.One2many('process.wip.log', 'wip_id', string="WIP History", readonly="True")

    _sql_constraints = [
        ('unique_sale_order_id', 'unique(sale_order_id)', 'A WIP record can only be created for a sale order once.')
    ]

    """
    This field will be backward manipulated from warehouse.task when the Flash Express order is created.
    """
    flash_express_order_id = fields.Char(
        string="Flash Express Order ID",
        help="This field is used to store the Flash Express order ID. "
            "It will be set when the Flash Express order is created.",
        # readonly=True,
    )

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
        for record in self:
            if record.status and record._origin.status:
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.status
                previous_status = record._origin.status
                is_valid_transition = preferred_status in wip_and_task_allowed_status_transition.get(previous_status, [])  # type: ignore
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.status}.")
                
    @api.onchange('flash_express_status')
    def _onchange_flash_express_status(self): 
        for record in self:
            if record.flash_express_status and record._origin.flash_express_status:
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.flash_express_status
                previous_status = record._origin.flash_express_status
                is_valid_transition = preferred_status in wip_and_task_allowed_status_transition.get(previous_status, [])  # type: ignore
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.flash_express_status}.")
    