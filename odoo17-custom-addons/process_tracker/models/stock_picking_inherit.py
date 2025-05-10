from odoo import models
from odoo.exceptions import ValidationError


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    def do_print_picking(self):
        res = super().do_print_picking()

        for picking in self:
            # 1. Find related sale order id
            sale_order_id = picking.sale_id.id # added line
            if sale_order_id:
                # 2. Use related sale_order id to find the related wip
                related_wip = self.env['process.wip'].search([
                    ('sale_order_id', '=', sale_order_id)
                ], limit=1) # changed search logic
                # 3. Change related wip status to be 'kitting'
                if related_wip:
                    related_wip.write({'status': 'kitting'})
        return res