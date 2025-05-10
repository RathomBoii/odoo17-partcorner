from odoo import models
from odoo.exceptions import ValidationError


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    def do_print_picking(self):
        res = super().do_print_picking()

        for picking in self:
            related_wip = self.env['process.wip'].search([
                ('delivery_id', '=', picking.id)
            ], limit=1) 
            if related_wip:
                related_wip.write({'status': 'kitting'})
        return res