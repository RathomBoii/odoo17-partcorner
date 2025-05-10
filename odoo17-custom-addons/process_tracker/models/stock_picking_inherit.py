from odoo import models, api
from odoo.exceptions import UserError


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
    
    @api.model
    def create(self, vals):
        """
        Override the create method to auto-validate the picking.
        """
        picking = super().create(vals)  # Create the picking first

        # Auto-validate the picking
        try:
            # 1. Find the related sale order
            sale_order_id = picking.sale_id.id
            if sale_order_id:
                # 2. Check if a process.wip record exists for the sale order
                wip_record = self.env['process.wip'].search([('sale_order_id', '=', sale_order_id)], limit=1)
                if wip_record:
                    picking.action_confirm()
                    picking.action_assign()
                    if picking.state in ('assigned', 'partially_available', 'waiting', 'confirmed'):
                        if not picking.move_line_ids:
                            picking.action_generate_picking_lines()
                        for move_line in picking.move_line_ids:
                            move_line.qty_done = move_line.product_uom_qty
                        picking.action_done()
                else:
                    raise UserError(f"No process.wip record found for sale order {picking.sale_id.name}.  Cannot auto-validate picking {picking.name}")
            else:
                raise UserError(f"No sale order found for picking {picking.name}. Cannot auto-validate.")

        except Exception as e:
            # Handle any errors during validation
            raise UserError(f"Error auto-validating picking {picking.name}: {e}")
        return picking
    
    