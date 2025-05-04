from odoo import models, api, fields
from odoo.exceptions import ValidationError

class ProcessWipInherit(models.Model):
    _inherit = 'process.wip'

    current_wip_status = fields.Char(string="WIP Status", compute="_compute_current_wip_status")

    @api.model
    # override process.wip's create() method
    def create(self, vals):
        record = super().create(vals)
        # Ensure sale_order_id is provided
        if not vals.get('sale_order_id'):
            raise ValidationError("The Sale Order field must be set.")

        model_to_create = 'warehouse.task'
        # Automatically create a related warehouse.task
        self.env[model_to_create].create({
            'sale_order_id': record.sale_order_id.id,
            'process_wip_id': record.id,
            'name': f"Task for WIP {record.id}",
            'status': 'order_received',
        })

        return record
    
    def write(self, vals):
        # Synchronize status changes with warehouse.task, prevent looping
        if 'status' in vals and not self.env.context.get('from_task'):
            for record in self:
                task = self.env['warehouse.task'].search([('process_wip_id', '=', record.id)], limit=1)
                if task:
                    task.with_context(from_wip=True).write({'status': vals['status']})
        return super().write(vals)
