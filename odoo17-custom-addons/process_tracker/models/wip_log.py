from odoo import models, fields

class ProcessWIPLog(models.Model):
    _name = 'process.wip.log'
    _description = 'WIP Status Log'

    wip_id = fields.Many2one('process.wip', required=True)
    previous_status = fields.Char()
    current_status = fields.Char()
    changed_by = fields.Many2one('res.users')
    changed_at = fields.Datetime(default=fields.Datetime.now)
