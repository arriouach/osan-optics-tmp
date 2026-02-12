from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ZidStockUpdateWizard(models.TransientModel):
    _name = 'zid.stock.update.wizard'
    _description = 'Zid Stock Update Wizard'

    zid_connector_id = fields.Many2one('zid.connector', string='Zid Connector', required=True)
    update_all_products = fields.Boolean(string='Update All Products', default=True)
    product_ids = fields.Many2many('zid.product', string='Products to Update')

    def action_update_stock(self):
        """Update stock quantities to Zid"""
        self.ensure_one()
        
        if not self.zid_connector_id.is_connected:
            raise UserError(_('Please connect to Zid first'))
        
        # Get products to update
        if self.update_all_products:
            products = self.env['zid.product'].search([
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ])
        else:
            products = self.product_ids
        
        if not products:
            raise UserError(_('No products to update'))
        
        # Update stock for each product
        success_count = 0
        error_count = 0
        errors = []
        
        for product in products:
            try:
                # Get Odoo product and calculate stock
                if product.odoo_product_id:
                    odoo_product = product.odoo_product_id
                    
                    # Get available quantity
                    qty_available = odoo_product.qty_available
                    
                    # Update stock in Zid through product template
                    if hasattr(odoo_product.product_tmpl_id, 'action_update_stock_to_zid'):
                        odoo_product.product_tmpl_id.action_update_stock_to_zid()
                        success_count += 1
                    else:
                        # Fallback: use product line if exists
                        product_lines = self.env['zid.product.line'].search([
                            ('zid_product_id', '=', product.zid_product_id),
                            ('zid_connector_id', '=', self.zid_connector_id.id)
                        ])
                        if product_lines:
                            for line in product_lines:
                                if hasattr(line, 'action_sync_stock'):
                                    line.action_sync_stock()
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(f"{product.name}: No sync method available")
                else:
                    error_count += 1
                    errors.append(f"{product.name}: No linked Odoo product")
                    
            except Exception as e:
                error_count += 1
                errors.append(f"{product.name}: {str(e)}")
        
        # Prepare result message
        message = _('Stock update completed:\n')
        message += _('✅ Success: %d products\n') % success_count
        if error_count > 0:
            message += _('❌ Errors: %d products\n') % error_count
            if errors:
                message += _('\nErrors:\n') + '\n'.join(errors[:5])
                if len(errors) > 5:
                    message += _('\n... and %d more errors') % (len(errors) - 5)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Update Complete'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
