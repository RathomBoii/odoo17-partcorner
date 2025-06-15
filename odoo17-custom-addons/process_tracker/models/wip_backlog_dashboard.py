from odoo import models, fields, api

class WIPBacklogDashboard(models.TransientModel):
    _name = 'wip.backlog.dashboard'
    _description = 'WIP and Backlog Dashboard'

    wip_ids = fields.Many2many('process.wip', string="WIP Records")
    backlog_ids = fields.Many2many('process.backlog', string="Backlog Records")
    wip_count = fields.Integer(string="Total WIP Records", compute="_compute_counts")
    backlog_count = fields.Integer(string="Total Backlog Records", compute="_compute_counts")

    @api.depends('wip_ids', 'backlog_ids')
    def _compute_counts(self):
        """Compute the counts of WIP and Backlog records."""
        for record in self:
            record.wip_count = len(record.wip_ids) # type: ignore
            record.backlog_count = len(record.backlog_ids) # type: ignore

    @api.model
    def default_get(self, fields): # type: ignore
        """Fetch WIP and Backlog records dynamically."""
        res = super(WIPBacklogDashboard, self).default_get(fields)

        # Fetch WIP records where status != 'done'
        wip_records = self.env['process.wip'].search([('status', '!=', 'done')])

        # Fetch Backlog records where status != 'transitioned'
        backlog_records = self.env['process.backlog'].search([('status', '!=', 'transitioned')])

        res.update({
            'wip_ids': [(6, 0, wip_records.ids)],
            'backlog_ids': [(6, 0, backlog_records.ids)],
        })
        return res