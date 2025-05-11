from odoo import models, api
from odoo.exceptions import UserError
# import logging
# _logger = logging.getLogger(__name__)


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    def do_print_picking(self):
        res = super().do_print_picking()
        # _logger.info("Print the Picking Id: %s", res)  # Add logging here
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
    
    # def button_validate(self):
    #     _logger.info("button_validate method called for picking: %s", self.name) #and here
    #     _logger.info("Picking detail: %s", self)
    #     _logger.info("Picking move_ids: %s", self.move_ids)
    #     _logger.info("Picking move_ids_without_package: %s", self.move_ids_without_package)
    #     _logger.info("Picking move_line_exist: %s", self.move_line_exist)
    #     _logger.info("Picking move_line_ids: %s", self.move_line_ids)
    #     _logger.info("Picking move_line_ids_without_package: %s", self.move_line_ids_without_package)
    #     _logger.info("Picking product_id: %s", self.product_id)
    #     res = super().button_validate()

        
    

    # @api.model
    # def create(self, vals):
    #     _logger.info("create method called with vals: %s", vals)  # Add logging here
    #     picking_record = super().create(vals)
    #     picking_record.button_validate()
    #     return picking_record
    
    