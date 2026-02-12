from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ZidProductLineSyncWizard(models.TransientModel):
    _name = 'zid.product.line.sync.wizard'
    _description = 'Sync Product Lines with Zid'
    
    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )
    
    line_ids = fields.Many2many(
        'zid.product.line',
        string='Lines to Sync',
        required=True,
        domain="[('product_template_id', '=', product_id)]"
    )
    
    sync_type = fields.Selection([
        ('create', 'Create in Zid'),
        ('update', 'Update in Zid'),
        ('stock', 'Update Stock Only'),
        ('full', 'Full Sync')
    ], string='Sync Type', default='full', required=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Get product from context
        if self.env.context.get('active_model') == 'product.template':
            product_id = self.env.context.get('active_id')
            if product_id:
                res['product_id'] = product_id
                
                # Get all lines for this product
                lines = self.env['zid.product.line'].search([
                    ('product_template_id', '=', product_id)
                ])
                res['line_ids'] = [(6, 0, lines.ids)]
        
        return res
    
    def action_sync(self):
        """Sync selected lines based on sync type"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('Please select at least one line to sync'))
        
        success_count = 0
        error_count = 0
        errors = []
        
        for line in self.line_ids:
            try:
                if self.sync_type == 'stock':
                    line.action_sync_stock()
                elif self.sync_type in ['create', 'update', 'full']:
                    line.sync_to_zid()
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"{line.store_name} - {line.location_name}: {str(e)}")
                _logger.error(f"Failed to sync line {line.id}: {str(e)}")
        
        # Prepare result message
        message = _('Sync completed: %d successful, %d failed') % (success_count, error_count)
        
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors)
            msg_type = 'warning' if success_count > 0 else 'danger'
        else:
            msg_type = 'success'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Result'),
                'message': message,
                'type': msg_type,
                'sticky': error_count > 0,
            }
        }


class ZidProductLineCreateWizard(models.TransientModel):
    _name = 'zid.product.line.create.wizard'
    _description = 'Create Product Lines for Multiple Stores'
    
    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )
    
    connector_ids = fields.Many2many(
        'zid.connector',
        string='Stores',
        required=True,
        domain=[('authorization_status', '=', 'connected')]
    )
    
    location_selection = fields.Selection([
        ('default', 'Default Location for Each Store'),
        ('all', 'All Locations for Each Store'),
        ('manual', 'Select Manually')
    ], string='Location Selection', default='default', required=True)
    
    # For manual selection
    location_ids = fields.Many2many(
        'zid.location',
        string='Locations'
    )
    
    # Default values
    default_price = fields.Float(
        string='Default Price',
        help='Leave empty to use product sale price'
    )
    
    is_published = fields.Boolean(
        string='Published by Default',
        default=True
    )
    
    track_inventory = fields.Boolean(
        string='Track Inventory',
        default=True
    )
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        if self.env.context.get('active_model') == 'product.template':
            product_id = self.env.context.get('active_id')
            if product_id:
                product = self.env['product.template'].browse(product_id)
                res['product_id'] = product_id
                res['default_price'] = product.list_price
        
        return res
    
    @api.onchange('connector_ids', 'location_selection')
    def _onchange_connector_ids(self):
        """Update location domain based on selected stores"""
        if self.connector_ids:
            domain = [('zid_connector_id', 'in', self.connector_ids.ids)]
            
            if self.location_selection == 'manual':
                return {'domain': {'location_ids': domain}}
            else:
                self.location_ids = False
                return {'domain': {'location_ids': domain}}
    
    def action_create_lines(self):
        """Create product lines based on selections"""
        self.ensure_one()
        
        if not self.connector_ids:
            raise UserError(_('Please select at least one store'))
        
        line_model = self.env['zid.product.line']
        created_lines = self.env['zid.product.line']
        
        for connector in self.connector_ids:
            # Determine locations based on selection
            if self.location_selection == 'default':
                locations = connector.default_location_id
                if not locations:
                    # Get first enabled location
                    locations = self.env['zid.location'].search([
                        ('zid_connector_id', '=', connector.id),
                        ('is_enabled', '=', True)
                    ], limit=1)
            elif self.location_selection == 'all':
                locations = self.env['zid.location'].search([
                    ('zid_connector_id', '=', connector.id),
                    ('is_enabled', '=', True)
                ])
            else:  # manual
                locations = self.location_ids.filtered(
                    lambda l: l.zid_connector_id == connector
                )
            
            if not locations:
                _logger.warning(f"No locations found for store {connector.store_name}")
                continue
            
            # Create lines for each location
            for location in locations:
                # Check if line already exists
                existing = line_model.search([
                    ('product_template_id', '=', self.product_id.id),
                    ('zid_connector_id', '=', connector.id),
                    ('zid_location_id', '=', location.id)
                ])
                
                if not existing:
                    line = line_model.create({
                        'product_template_id': self.product_id.id,
                        'zid_connector_id': connector.id,
                        'zid_location_id': location.id,
                        'zid_price': self.default_price or self.product_id.list_price,
                        'is_published': self.is_published,
                        'track_inventory': self.track_inventory,
                        'zid_sku': self.product_id.default_code,
                    })
                    created_lines |= line
        
        if created_lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('%d product lines created successfully') % len(created_lines),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('No new lines were created. Lines may already exist for selected store-location combinations.'))
