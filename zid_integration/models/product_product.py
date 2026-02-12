from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError
from dateutil import relativedelta
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    zid_variant_line_ids = fields.One2many('zid.variant.line', 'product_id')

    def action_open_update_wizard(self):
        """Open wizard to update this product in Zid"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Product in Zid'),
            'res_model': 'zid.product.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_ids': [(6, 0, self.ids)],
            }
        }

    def create_in_zid(self):
        """Create this product variant in Zid stores"""
        for product in self:
            # Use variant line to create in Zid
            if product.zid_variant_line_ids:
                for line in product.zid_variant_line_ids:
                    if not line.zid_variant_id:
                        line.create_in_zid()
            else:
                # No variant lines configured - inform user
                raise ValidationError(_(
                    'Product %s has no Zid variant lines configured. '
                    'Please configure which Zid stores/locations to sync to first.'
                ) % product.display_name)
        return True

    def update_in_zid(self):
        """Update this product variant in Zid"""
        for product in self:
            if product.zid_variant_line_ids:
                for line in product.zid_variant_line_ids:
                    if line.zid_variant_id:
                        # Update existing variant
                        line.action_sync_stock()
            else:
                raise ValidationError(_(
                    'Product %s has no Zid variant lines configured.'
                ) % product.display_name)
        return True

    def sync_from_zid(self):
        """Sync product data from Zid (if linked)"""
        for product in self:
            # Find linked Zid variants
            zid_variants = self.env['zid.variant'].search([
                ('odoo_product_id', '=', product.id)
            ])
            if zid_variants:
                for variant in zid_variants:
                    # Update Odoo product from Zid data
                    if variant.price:
                        product.lst_price = variant.price
                    if variant.cost:
                        product.standard_price = variant.cost
                    if variant.barcode and not product.barcode:
                        product.barcode = variant.barcode
            else:
                raise ValidationError(_(
                    'Product %s is not linked to any Zid variant.'
                ) % product.display_name)
        return True

    def create_in_all_zid_stores(self):
        """Create this product in all connected Zid stores"""
        self.ensure_one()
        
        # Get all connected Zid connectors
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ])
        
        if not connectors:
            raise ValidationError(_('No connected Zid stores found.'))
        
        # Create variant line for each connector
        for connector in connectors:
            # Get default location
            default_location = connector.zid_location_ids.filtered('is_default')
            if not default_location:
                default_location = connector.zid_location_ids[:1]
            
            if default_location:
                # Create variant line
                self.env['zid.variant.line'].create({
                    'product_id': self.id,
                    'zid_connector_id': connector.id,
                    'zid_location_id': default_location.id,
                    'zid_sku': self.default_code or f'ODOO-{self.id}',
                    'zid_price': self.lst_price,
                    'is_published': True,
                })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Product configured for %d Zid store(s)') % len(connectors),
                'type': 'success',
            }
        }

    def sync_all_stock_to_zid(self):
        """Sync stock to all configured Zid stores"""
        for product in self:
            if product.zid_variant_line_ids:
                for line in product.zid_variant_line_ids:
                    try:
                        line.action_sync_stock()
                    except Exception as e:
                        _logger.error(f"Failed to sync stock for {product.display_name} to {line.zid_connector_id.store_name}: {str(e)}")
            else:
                raise ValidationError(_(
                    'Product %s has no Zid variant lines configured.'
                ) % product.display_name)
        return True

