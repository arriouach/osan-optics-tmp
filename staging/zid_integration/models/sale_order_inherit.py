from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Zid Integration Fields
    zid_order_ref = fields.Char(
        string='Zid Order ID',
        readonly=True,
        help='Zid Order ID (numeric reference from Zid system)'
    )
    zid_order_id = fields.Many2one(
        'zid.sale.order',
        string='Zid Order',
        readonly=True,
        help='Link to the Zid order record'
    )

    def action_confirm(self):
        """Override to sync status to Zid on confirmation"""
        res = super(SaleOrder, self).action_confirm()
        
        for order in self:
            # Check if this is a Zid order
            zid_order = self.env['zid.sale.order'].search([('sale_order_id', '=', order.id)], limit=1)
            
            if zid_order and zid_order.zid_connector_id.sync_status_to_zid:
                # Map Odoo 'sale' state to Zid 'preparing' or 'ready'
                # For now, let's map to 'preparing'
                zid_order.zid_connector_id.update_order_status(zid_order.zid_order_id, 'preparing')
                
        return res

    def action_view_zid_order(self):
        """Open the related Zid order"""
        self.ensure_one()
        if self.zid_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.sale.order',
                'res_id': self.zid_order_id.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'context': {'create': False},
            }
        return False
