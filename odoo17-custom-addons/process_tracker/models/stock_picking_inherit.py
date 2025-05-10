from odoo import models
from odoo.exceptions import ValidationError


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    def write(self, vals):
        res = super().write(vals)  # Important to call super

        if 'state' in vals and vals['state'] != 'draft': #update delivery_id only when not draft
            for picking in self:
                # origin is the sale order
                if picking.origin:
                    related_wip = self.env['process.wip'].search([
                        ('sale_order_id.name', '=', picking.origin)  # changed from sale_order_id to sale_order_id.name
                    ], limit=1)
                    if related_wip:
                        related_wip.write({'delivery_id': picking.id})
        return res

    def do_print_picking(self):
        res = super().do_print_picking()

        for picking in self:
            related_wip = self.env['process.wip'].search([
                ('delivery_id', '=', picking.id)
            ], limit=1) # added limit = 1
            if related_wip:
                related_wip.write({'status': 'kitting'})
        return res