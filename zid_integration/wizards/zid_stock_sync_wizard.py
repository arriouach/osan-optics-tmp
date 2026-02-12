from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidStockSyncWizard(models.TransientModel):
    _name = 'zid.stock.sync.wizard'
    _description = 'Manual Zid Stock Sync'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )

    sync_all_locations = fields.Boolean(
        string='Sync All Mapped Locations',
        default=True
    )

    location_ids = fields.Many2many(
        'stock.location',
        string='Locations to Sync',
        domain=[('usage', '=', 'internal')]
    )

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            result['product_id'] = self.env.context['active_id']
        return result

    @api.onchange('sync_all_locations')
    def _onchange_sync_all_locations(self):
        if self.sync_all_locations:
            self.location_ids = False

    def action_sync_stock(self):
        """Manually sync stock to Zid"""
        self.ensure_one()
        
        if not self.product_id.zid_product_id:
            raise UserError(_('Product does not exist in Zid. Please create it first.'))
        
        if not self.product_id.zid_connector_id:
            raise UserError(_('Product is not connected to any Zid store.'))
        
        # Get mappings
        mappings = self.env['zid.location.mapping'].search([
            ('product_id', '=', self.product_id.id),
            ('is_active', '=', True)
        ])
        
        if not mappings:
            raise UserError(_('No active location mappings found. Please setup location mappings first.'))
        
        # Filter by selected locations if needed
        if not self.sync_all_locations and self.location_ids:
            mappings = mappings.filtered(lambda m: m.odoo_location_id in self.location_ids)
        
        success_count = 0
        error_count = 0
        
        for mapping in mappings:
            try:
                # Get current quantity
                quants = self.env['stock.quant'].search([
                    ('product_id.product_tmpl_id', '=', self.product_id.id),
                    ('location_id', '=', mapping.odoo_location_id.id)
                ])
                
                total_qty = sum(quants.mapped('quantity'))
                
                # Sync to Zid
                self._sync_to_zid(mapping, total_qty)
                success_count += 1
                
            except Exception as e:
                _logger.error(f"Failed to sync location {mapping.odoo_location_id.name}: {str(e)}")
                error_count += 1
        
        # Show result
        message = _('Sync completed: %d successful, %d failed') % (success_count, error_count)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Sync Result'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
            }
        }

    def _sync_to_zid(self, mapping, quantity):
        """Sync stock to Zid for a specific mapping"""
        product = mapping.product_id
        connector = product.zid_connector_id
        
        # Prepare data
        update_data = {
            'stocks': [{
                'available_quantity': int(quantity),
                'is_infinite': False,
                'location': mapping.zid_location_id.zid_location_id
            }]
        }
        
        # Call API
        response = connector.api_request(
            endpoint=f'products/{product.zid_product_id}/',
            method='PATCH',
            data=update_data
        )
        
        # Update mapping record
        mapping.write({
            'last_synced_qty': quantity,
            'last_sync_date': fields.Datetime.now()
        })
        
        # Create log
        self.env['zid.stock.sync.log'].create({
            'product_id': product.id,
            'odoo_location_id': mapping.odoo_location_id.id,
            'zid_location_id': mapping.zid_location_id.id,
            'old_quantity': mapping.last_synced_qty,
            'new_quantity': quantity,
            'sync_status': 'success',
        })
