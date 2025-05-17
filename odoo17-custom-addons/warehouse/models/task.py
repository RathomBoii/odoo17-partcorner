from odoo import models, fields, api
from odoo.exceptions import ValidationError

class WarehouseTask(models.Model):
    _name = 'warehouse.task'
    _description = 'Warehouse Task'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    process_wip_id = fields.Many2one('process.wip', string='Process WIP', required=True)
    name = fields.Char(string="Task Name", required=True)
    assignee = fields.Many2one('res.users', string='Assignee')
    status = fields.Selection([
        ('order_received', 'Order Received'), 
        ('kitting', 'Kitting'), 
        ('checking', 'Checking'), 
        ('packing', 'Packing'),
        ('booking', 'Booking'), 
        ('pick_up_by_courier', 'Pick Up By Courier'), 
        ('done', 'Done')
    ], default='order_received')

    delivery_id = fields.Many2one('stock.picking', related='process_wip_id.delivery_id')

    customer = fields.Many2one('res.partner', related='sale_order_id.partner_id', string="Customer", readonly=True)

    shipping_partner_id = fields.Many2one(
        'res.partner',
        related='sale_order_id.partner_shipping_id',
        string="Shipping Address",
        readonly=True,
        store=True  # Important for searching and potentially better performance
    )

    delivery_contact_name = fields.Char(related='shipping_partner_id.name', string="Delivery Contact", readonly=True, store=True)
    delivery_phone = fields.Char(related='shipping_partner_id.phone', string="Delivery Phone", readonly=True, store=True)
    delivery_email = fields.Char(related='shipping_partner_id.email', string="Delivery Email", readonly=True, store=True)
    delivery_street = fields.Char(related='shipping_partner_id.street', string="Delivery Street", readonly=True, store=True)
    delivery_street2 = fields.Char(related='shipping_partner_id.street2', string="Delivery Street 2", readonly=True, store=True)
    delivery_city = fields.Char(related='shipping_partner_id.city', string="Delivery City", readonly=True, store=True)
    delivery_state_id = fields.Many2one(related='shipping_partner_id.state_id', string="Delivery State", readonly=True, store=True)
    delivery_zip = fields.Char(related='shipping_partner_id.zip', string="Delivery Zip", readonly=True, store=True)
    delivery_country_id = fields.Many2one(related='shipping_partner_id.country_id', string="Delivery Country", readonly=True, store=True)



    allowed_status_transition_dict = {
            'order_received': ['kitting'],
            'kitting': ['checking'],
            'checking': ['packing'],
            'packing': ['booking'],
            'booking': ['pick_up_by_courier'],
            'pick_up_by_courier': ['done'],
            'done': []
        }
    



    def write(self, vals):
        # Synchronize status changes with process.wip
        if 'status' in vals and not self.env.context.get('from_wip'):
            for record in self:
                if record.process_wip_id:
                    record.process_wip_id.with_context(from_task=True).write({'status': vals['status']})
        return super().write(vals)


    # def action_set_status(self):
    #     """Set status dynamically via button."""
    #     new_status = self.env.context.get('new_status')
    #     if not new_status:
    #         raise ValidationError("No status provided.")
    #     for record in self:
    #         record._validate_and_update_status(new_status)

   

    # def _validate_and_update_status(self, new_status):
    #     """Private method to validate and update status."""
    #     for record in self:
    #         previous_status = record.status
    #         if not record.allowed_status_transition_dict:
    #             raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี allowed_status_transition_dict.")
            
    #         allowed_status_transition_dict = record.allowed_status_transition_dict
    #         if new_status not in allowed_status_transition_dict.get(previous_status, []):
    #             raise ValidationError(
    #                 f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {new_status}."
    #             )
    #         allowed_status_transition_dict = record.allowed_status_transition_dict
    #         record.status = new_status
    #         if record.process_wip_id:
    #             record.process_wip_id.write({'status': new_status})
    #         else:
    #             raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี process_wip_id.")
            
    @api.onchange('status')
    def _onchange_status(self):
        # allowed_status_transition_dict = {
        #     'order_received': ['kitting'],
        #     'kitting': ['checking'],
        #     'checking': ['packing'],
        #     'packing': ['booking'],
        #     'booking': ['pick_up_by_courier'],
        #     'pick_up_by_courier': ['done'],
        #     'done': []
        # }

        for record in self:
            if not record.allowed_status_transition_dict:
                raise ValidationError("ไม่สามารถเปลี่ยน status ได้ เนื่องจากไม่มี allowed_status_transition_dict.")
            if record.status and record._origin.status:
                allowed_status_transition_dict = record.allowed_status_transition_dict
                # check if there are both original status and preferred status
                # check if prefered status in allowed status list for original status 
                preferred_status = record.status
                previous_status = record._origin.status
                is_valid_transition = preferred_status in allowed_status_transition_dict.get(previous_status,[])
                if not is_valid_transition:
                    raise ValidationError(f"ไม่สามารถเปลี่ยน status ข้ามขั้นตอนได้ จาก {previous_status} ไปสู่ {record.status}.")


# //
# to integrated
# 1.create order -> individual
# 2.print label -> individual
# 3.notify courier -> batch ? 
# 4.courier status -> individual 
#   - attach url in sale portal (more field on WIP)
# 
# Todo
# 1.add view
# 2.show customer information in task model and enable copy button
# 2.read the API docs
# 3.add field
# 4.add Task method to call API
# 5.Dev Test
# #
