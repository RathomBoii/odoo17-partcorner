from odoo import models
from odoo.exceptions import ValidationError


class SockPickingInherit(models.Model):

    _inherit = 'stock.picking'


    def do_print_picking(self):
        res = super().do_print_picking()

        for picking in self:
            related_wip = self.env['process.wip'].search([
                (
                    'delivery_id', '=', picking.id
                )
            ])

            related_wip.write({'status': 'kitting'}) if related_wip else False

        return res