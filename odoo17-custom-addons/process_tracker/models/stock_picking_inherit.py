from odoo import models, api
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
    
    @api.model
    def create(self, vals):
        """
        Override the create method to auto-validate the picking.
        """
        picking = super().create(vals)  # Create the picking first

        # Auto-validate the picking
        try:
            picking.action_confirm()  # Confirm the picking
            picking.action_assign()   # Assign the picking (reserve products)
            # Check if the picking is ready to be processed
            # if picking.state == 'assigned':
            #     # Process the picking to create move lines if they don't exist
            #     if not picking.move_line_ids:
            #         picking.action_generate_picking_lines()

            #     # Loop through each move line and set the quantity done
            #     for move_line in picking.move_line_ids:
            #         move_line.qty_done = move_line.product_uom_qty

            #     picking.action_done()        # Validate the picking
        except Exception as e:
            # Handle any errors during validation
            raise UserError(f"Error auto-validating picking {picking.name}: {e}")
        return picking