from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override to sync status to Zid on delivery validation"""
        res = super(StockPicking, self).button_validate()
        
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.state == 'done':
                # Find related Zid order via Sale Order
                sale_order = picking.sale_id
                if sale_order:
                    zid_order = self.env['zid.sale.order'].search([('sale_order_id', '=', sale_order.id)], limit=1)
                    
                    if zid_order and zid_order.zid_connector_id.sync_status_to_zid:
                        # Map Odoo 'done' delivery to Zid 'ready' or 'indelivery'
                        # 'ready' means ready for pickup/shipping
                        zid_order.zid_connector_id.update_order_status(zid_order.zid_order_id, 'ready')
                        
        return res
