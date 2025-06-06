from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging


_logger = logging.getLogger(__name__)

class PickupRequest(models.Model):
    _name = 'warehouse.pickup_request'
    _description = 'A collection of task ids which we will make a request to courier to pickup.'

    name = fields.Char(string='Request Name', required=True, copy=False, default=lambda self: _('New'))

    task_ids = fields.One2many(
        'warehouse.task',
        'pickup_request_id', # This is the field on the 'warehouse.task' model that links back here.
        string='Tasks in this Request',
        domain="[('status', '=', 'booking'), ('is_selected', '=', False)]",
        readonly=False, # Allow editing through the UI
    )

    # This Many2many field is for selecting *new* tasks to add to the request.
    # The domain ensures only 'booking' status tasks that are not yet selected are available.
    selectable_tasks = fields.Many2many(
        'warehouse.task',
        string='Selectable Tasks',
        domain="[('status', '=', 'booking'), ('is_selected', '=', False)]",
        help="Select tasks in 'Booking' status that are not yet assigned to any pickup request. Once selected, they will be moved to 'Tasks in this Request'."
    )

    # A computed field to show the count of tasks
    task_count = fields.Integer(string='Number of Tasks', compute='_compute_task_count', store=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested to Courier'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True) # Added tracking for status changes

    # Method to update task_ids when selectable_tasks changes
    @api.onchange('selectable_tasks')
    def _onchange_selectable_tasks(self):
        if self.selectable_tasks:
            # Add newly selected tasks to task_ids
            new_tasks = self.selectable_tasks - self.task_ids
            if new_tasks:
                self.task_ids += new_tasks
                # Clear selectable_tasks after moving them to task_ids
                self.selectable_tasks = [(5, 0, 0)] 
            
            # Remove tasks from task_ids if they were unselected from selectable_tasks 
            # (though with the current logic, this might be less common as they move directly)
            # This part needs careful consideration if tasks can be "unselected" from task_ids directly.
            # For simplicity, we assume tasks are added via selectable_tasks and then managed via task_ids.

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    # Constraint to prevent a task from being in more than one pickup request
    @api.constrains('task_ids')
    def _check_unique_tasks(self):
        for request in self:
            # Check for tasks that are duplicated within this request (shouldn't happen with O2M)
            # or tasks that are assigned to another pickup request
            if request.task_ids:
                # Find other pickup requests that contain any of these tasks
                other_requests = self.env['warehouse.pickup_request'].search([
                    ('id', '!=', request.id),
                    ('task_ids', 'in', request.task_ids.ids)
                ])
                if other_requests:
                    # Get the names of the conflicting tasks and requests
                    conflicting_tasks = request.task_ids.filtered(lambda t: t.pickup_request_id and t.pickup_request_id != request)
                    if conflicting_tasks:
                        raise ValidationError(
                            _("The following tasks are already part of another pickup request: %s. Please remove them from this request or the other request first.") % ", ".join(conflicting_tasks.mapped('name'))
                        )
                    

    # NEW OR MODIFIED WRITE METHOD
    def write(self, vals):
        if 'task_ids' in vals:
            # Separate the commands for task_ids
            task_commands = vals.get('task_ids', [])
            
            tasks_to_unlink = self.env['warehouse.task']
            new_task_commands = []

            for command in task_commands:
                if command[0] == 2:  # Command (2, ID) means delete
                    task_id = command[1]
                    task = self.env['warehouse.task'].browse(task_id)
                    if task.exists():
                        tasks_to_unlink += task
                        # DO NOT ADD THIS COMMAND TO new_task_commands
                        # We handle the unlinking manually
                    else:
                        _logger.warning(f"Attempted to unlink non-existent task with ID: {task_id}")
                elif command[0] == 3: # Command (3, ID) means unlink, without deleting the record
                    task_id = command[1]
                    task = self.env['warehouse.task'].browse(task_id)
                    if task.exists():
                        tasks_to_unlink += task
                    # Also don't add (3, ID) to new_task_commands if we handle it
                    else:
                         _logger.warning(f"Attempted to unlink non-existent task with ID: {task_id}")
                else:
                    # Keep other commands (0, 1, 4, 5, 6) as they are
                    new_task_commands.append(command)
            
            # Update vals with filtered commands for task_ids
            vals['task_ids'] = new_task_commands
            
            # Perform the parent write operation
            res = super().write(vals)

            # After the write, perform the actual unlinking of the detected tasks
            if tasks_to_unlink:
                _logger.info(f"Unlinking tasks from pickup request: {tasks_to_unlink.mapped('name')}")
                # Set pickup_request_id to False for these tasks
                tasks_to_unlink.write({'pickup_request_id': False})
                # is_selected will recompute automatically
            return res
        else:
            # If 'task_ids' is not in vals, proceed with standard write
            return super().write(vals)

        return res

    # Actions to manage the status
    def action_request_pickup(self):
        for rec in self:
            if not rec.task_ids:
                raise UserError(_("You cannot request a pickup without any tasks selected."))
            # Here you would typically integrate with a courier API to request pickup for all tasks
            # If successful, change status and potentially update task statuses
            rec.write({'status': 'requested'})
            # You might want to transition the status of associated tasks here
            rec.task_ids.write({'status': 'pick_up_by_courier'}) # Example: update task status

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('warehouse.pickup_request') or _('New')
        return super().create(vals)


