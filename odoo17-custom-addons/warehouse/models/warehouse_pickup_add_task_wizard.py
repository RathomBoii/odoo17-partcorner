from odoo import models, fields, api, _

class WarehousePickupAddTaskWizard(models.TransientModel):
    _name = 'warehouse.pickup_add_task_wizard'
    _description = 'Wizard to Add Existing Tasks to Pickup Request'

    pickup_request_id = fields.Many2one(
        'warehouse.pickup_request',
        string="Pickup Request",
        required=True,
        readonly=True,
    )
    task_ids_to_add = fields.Many2many(
        'warehouse.task',
        string="Available Tasks to Add",
        domain="[('pickup_request_id', '=', False), ('status', 'in', ['booking', 'new'])]",
        help="Select tasks that are not yet assigned to any pickup request."
    )

    def action_add_selected_tasks(self):
        self.ensure_one()
        if self.task_ids_to_add:
            self.task_ids_to_add.write({'pickup_request_id': self.pickup_request_id.id})
        return {'type': 'ir.actions.act_window_close'}