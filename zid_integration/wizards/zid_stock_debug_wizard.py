from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidStockDebugWizard(models.TransientModel):
    _name = 'zid.stock.debug.wizard'
    _description = 'Debug Zid Stock Issues'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )

    debug_info = fields.Text(
        string='Debug Information',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        
        if self.env.context.get('active_id'):
            product = self.env['product.template'].browse(self.env.context['active_id'])
            result['product_id'] = product.id
            
            # Gather debug information
            debug_lines = []
            debug_lines.append("=== PRODUCT INFORMATION ===")
            debug_lines.append(f"Product: {product.name}")
            debug_lines.append(f"Zid Product ID: {product.zid_product_id}")
            debug_lines.append(f"Auto Sync Enabled: {product.auto_sync_stock}")
            debug_lines.append("")
            
            # Get Odoo stock quantities
            debug_lines.append("=== ODOO STOCK QUANTITIES ===")
            locations = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('zid_location_id', '!=', False)
            ])
            
            total_odoo_qty = 0
            for location in locations:
                quants = self.env['stock.quant'].search([
                    ('product_id.product_tmpl_id', '=', product.id),
                    ('location_id', '=', location.id)
                ])
                qty = sum(quants.mapped('quantity'))
                if qty > 0:
                    debug_lines.append(f"{location.name}: {qty} units (Zid Location: {location.zid_location_id.name_en})")
                    total_odoo_qty += qty
            
            debug_lines.append(f"Total Odoo Quantity: {total_odoo_qty}")
            debug_lines.append("")
            
            # Get Zid stock quantities
            if product.zid_product_id and product.zid_connector_id:
                debug_lines.append("=== ZID STOCK QUANTITIES ===")
                try:
                    response = product.zid_connector_id.api_request(
                        endpoint=f'products/{product.zid_product_id}',
                        method='GET'
                    )
                    
                    if response:
                        debug_lines.append(f"Total Zid Quantity: {response.get('quantity', 0)}")
                        if 'stocks' in response:
                            for stock in response['stocks']:
                                loc_name = stock.get('location', {}).get('name', {}).get('en', 'Unknown')
                                qty = stock.get('available_quantity', 0)
                                loc_id = stock.get('location', {}).get('id', 'No ID')
                                debug_lines.append(f"- {loc_name} (ID: {loc_id}): {qty} units")
                        else:
                            debug_lines.append("No stock information in Zid response")
                    
                except Exception as e:
                    debug_lines.append(f"Error fetching Zid data: {str(e)}")
            else:
                debug_lines.append("Product not connected to Zid")
            
            result['debug_info'] = '\n'.join(debug_lines)
        
        return result

    def action_refresh(self):
        """Refresh debug information"""
        self.ensure_one()
        
        # Re-run default_get logic
        defaults = self.default_get(['debug_info'])
        self.debug_info = defaults.get('debug_info', '')
        
        return {
            'type': 'ir.actions.do_nothing',
        }

    def action_force_sync(self):
        """Force sync all locations"""
        self.ensure_one()
        
        locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('zid_location_id', '!=', False)
        ])
        
        sync_results = []
        
        for location in locations:
            quants = self.env['stock.quant'].search([
                ('product_id.product_tmpl_id', '=', self.product_id.id),
                ('location_id', '=', location.id)
            ])
            
            qty = sum(quants.mapped('quantity'))
            if qty >= 0:  # Sync even zero quantities
                try:
                    response = self.product_id.update_stock_in_zid(
                        location.zid_location_id.zid_location_id,
                        qty
                    )
                    sync_results.append(f"✓ {location.name}: Synced {qty} units")
                except Exception as e:
                    sync_results.append(f"✗ {location.name}: Error - {str(e)}")
        
        # Refresh debug info
        self.action_refresh()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Results'),
                'message': '\n'.join(sync_results),
                'type': 'info',
                'sticky': True,
            }
        }
